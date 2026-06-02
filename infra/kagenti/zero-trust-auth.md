# Zero Trust Authentication Architecture

How AuthBridge, SPIFFE, and token exchange secure agent-to-agent and agent-to-tool communication in this project.

## Overview

Kagenti AuthBridge injects zero-trust authentication into every agent at deploy time via sidecar injection. Each agent pod gets: `proxy-init` (init container for iptables), `envoy-proxy` (inbound JWT validation, outbound token exchange), and `spiffe-helper` (SPIFFE SVID from SPIRE). Agent code is auth-unaware — all validation happens at the infrastructure layer.

## Current Architecture: JWT Passthrough

```
User (browser)
  → Keycloak login (PKCE) → JWT with realm_access.roles
  → frontend → campaign-api → campaign-director
      ↓
  Agent A ──(original JWT)──→ Agent B
              AuthBridge          AuthBridge
              inbound: validate   inbound: validate
              outbound: passthrough (no exchange)
```

- **Inbound**: AuthBridge validates JWT signature, issuer, audience (`kagenti`)
- **Outbound**: No `authproxy-routes` configured → original JWT passes through unchanged
- **User roles preserved**: `realm_access.roles` (e.g. `platinum-access`) available at every hop

### Why Passthrough (Not Token Exchange)

Keycloak V2 token exchange (RFC 8693) replaces the original JWT with a new one scoped to the target audience. The exchanged token **loses `realm_access.roles`** — Keycloak does not execute `oidc-usermodel-realm-role-mapper` during exchange. This breaks per-user authorization (e.g. alice has `platinum-access`, bob does not).

## AuthBridge Components

| Component | Type | Role |
|-----------|------|------|
| `proxy-init` | Init container | Sets up iptables to redirect traffic through envoy |
| `envoy-proxy` | Sidecar | Inbound JWT validation, outbound token exchange (if configured) |
| `spiffe-helper` | Sidecar | Obtains SPIFFE SVID from SPIRE, writes JWT-SVID to `/opt/jwt_svid.token` |
| `authbridge-config` | ConfigMap | ISSUER, EXPECTED_AUDIENCE, KEYCLOAK_URL |
| `spiffe-helper-config` | ConfigMap | SPIRE agent socket, jwt_audience (must match Keycloak issuer URL) |
| `authproxy-routes` | ConfigMap (optional) | Outbound token exchange routes |

## authproxy-routes (Disabled)

Token exchange routes are **not enabled** in this project. Example from the demo reference:

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: authproxy-routes
data:
  routes.yaml: |
    - host: "mongodb-mcp"             # match outbound request Host
      target_audience: "mongodb-tool"  # token exchange audience
      token_scopes: "openid mongodb-tool-aud mongodb-full-access"
```

When enabled, AuthBridge outbound intercepts requests matching `host`, performs Keycloak token exchange using the agent's SPIFFE SVID as client credential, and replaces the Authorization header with the exchanged token.

**Why disabled**: `token_scopes` is static (same for all users), and `realm_access.roles` is lost in the exchanged token. Per-user access control (platinum vs non-platinum) cannot be enforced.

## Per-User Authorization: mongodb-mcp

`mongodb-mcp` implements data-level filtering based on JWT claims:

```
JWT → parse realm_access.roles → has "platinum-access"?
  → yes: return all customers (including platinum tier)
  → no:  filter out platinum tier customers
```

- Alice (has `platinum-access` role) → sees all customers
- Bob (no `platinum-access` role) → platinum customers filtered out
- Fallback: also checks `scope` claim for future SPIFFE exchange compatibility

See `mongodb-mcp/app/server.py` → `filter_customers_by_user_perm()`.

## Future: Delegation Model

### Current State of the Industry

Red Hat Emerging Technologies published a [zero trust demo](https://github.com/redhat-et/zero-trust-agent-demo) demonstrating a **permission intersection** model using nested `act` claims (RFC 8693). This demo runs on OpenShift with kagenti for agent discovery, but implements its own delegation infrastructure (OPA + credential-gateway) — it does **not** use kagenti AuthBridge for delegation.

### Nested `act` Claims (RFC 8693)

The delegation model nests the original user's identity inside each exchanged token:

```json
{
  "sub": "spiffe://cluster/ns/marketing/sa/creative-producer",
  "act": {
    "sub": "alice",
    "roles": ["platinum-access", "admin"]
  }
}
```

Multi-hop delegation chains nest further, enabling audit trails and progressive permission narrowing.

### Permission Intersection

```
Effective Permissions = User Permissions ∩ Agent Capabilities
```

- Alice has `[platinum-access, admin]`
- Agent configured with capabilities `[platinum-access]`
- Effective: `[platinum-access]` — agent can only **reduce** permissions, never expand

### What Exists Today vs What's Planned

| Component | Status | Details |
|-----------|--------|---------|
| AuthBridge outbound token exchange (audience-scoped) | ✅ Shipped | RFC 8693 exchange, replaces token with one scoped to target audience |
| AuthBridge nested `act` claims | ❌ Not implemented | Demo uses separate credential-gateway, not AuthBridge |
| Keycloak delegation semantics | ❌ [Under discussion](https://github.com/keycloak/keycloak/discussions/43108) | Standard token exchange (26.2) does not support `act` claims |
| OPA permission intersection | ✅ Demo only | Implemented in redhat-et/zero-trust-agent-demo, not part of kagenti |
| Transactional tokens | 🔄 Planned | Kagenti team mentioned as future direction |

### Token Exchange Experiment (Verified 2026-05-31)

We tested the full AuthBridge token exchange pipeline end-to-end:

**Setup:**

1. MCP Gateway port temporarily changed from 8080 to 8090 — proxy-init excludes port 8080 (`OUTBOUND_PORTS_EXCLUDE`) because agents listen on 8080; port 8090 is intercepted by envoy-proxy. Reverted to 8080 after experiment (kagenti Helm chart hardcodes Gateway port, requiring manual patch on every install)
2. SPIFFE trust domain fixed from `localtest.me` to actual cluster domain (`signatureVerification.spireTrustDomain` in kagenti Helm chart)
3. Created `mcp-gateway` Keycloak client (target audience) + `mcp-gateway-aud` scope with audience mapper
4. Assigned `mcp-gateway-aud` + `roles` scope to all agent SPIFFE clients
5. Created `authproxy-routes` ConfigMap with `host: mcp-gateway-istio.gateway-system.svc, target_audience: mcp-gateway`

**Results:**

| Step | Result |
|------|--------|
| iptables intercepts outbound to port 8090 | ✅ |
| envoy-proxy matches host in routes.yaml | ✅ |
| envoy ext_proc calls Keycloak token exchange | ✅ |
| Keycloak returns exchanged token (`aud: mcp-gateway`) | ✅ |
| Exchanged token has `preferred_username: alice` | ✅ |
| **Exchanged token has `realm_access.roles`** | **❌ Empty** |

**Root cause:** Keycloak's standard token exchange (RFC 8693) does not execute protocol mappers during the exchange grant type. Both `oidc-usermodel-realm-role-mapper` (`realm_access.roles`) and `oidc-group-membership-mapper` (`groups`) produce empty claims in the exchanged token. The scopes are correctly assigned to the target client with the right mappers — Keycloak simply skips mapper execution for the token exchange grant.

The redhat-et/zero-trust-agent-demo uses `groups` claim (not `realm_access.roles`) for permission intersection, but faces the same limitation — the demo's AuthBridge integration (ADR-0010, status: Proposed) has not resolved this at the Keycloak level.

**Conclusion:** Token exchange works mechanically but loses all user attribute claims, breaking per-user authorization. Rolled back `authproxy-routes` — JWT passthrough remains the correct approach.

### Why We Use JWT Passthrough

AuthBridge outbound token exchange (`authproxy-routes`) is not configured because:

1. **All user claims are lost** (verified): Keycloak's standard token exchange does not execute protocol mappers (`oidc-usermodel-realm-role-mapper`, `oidc-group-membership-mapper`). The exchanged token's `realm_access.roles` and `groups` are empty regardless of client scope configuration. The redhat-et/zero-trust-agent-demo faces the same limitation.

2. **No delegation identity**: The exchanged token's `sub` is the original user, but `azp` becomes the agent's SPIFFE ID. Without nested `act` claims, there is no cryptographic proof of the delegation chain.

3. **No permission intersection engine**: No OPA or policy engine integrated into kagenti to compute per-hop permission intersections.

JWT passthrough preserves the original user JWT (with `realm_access.roles`) at every hop. Combined with application-level `filter_customers_by_user_perm()`, this is the correct interim approach until Keycloak supports role propagation in token exchange or kagenti implements nested `act` claims.

## MCP Gateway for Tools

### Architecture (v0.7.0-rc2)

MCP Gateway v0.7.0 introduced `MCPGatewayExtension` which auto-creates:
- `mcp-gateway-route` HTTPRoute → routes `/mcp` to the broker
- EnvoyFilter → ext_proc for MCP protocol parsing and tool call routing

Agents connect to the Gateway envoy (`mcp-gateway-istio.gateway-system.svc:8080/mcp`). The ext_proc router parses `tools/call` requests and routes them to the correct backend MCP server via Istio.

**Current usage**: Agents call tools through Gateway (`mcp-gateway-istio.gateway-system.svc:8080/mcp`). MCP Inspector browses tools via broker. Agent code defaults to `localhost` for local dev; k8s.yaml overrides point to the Gateway address.

**Port 8080**: MCP Gateway uses the default port 8080 (set by kagenti Helm chart). AuthBridge's proxy-init excludes port 8080 from iptables outbound redirection (`OUTBOUND_PORTS_EXCLUDE`), so outbound traffic to the Gateway bypasses envoy-proxy. This means AuthBridge token exchange cannot intercept agent-to-Gateway calls, but this is acceptable because token exchange loses `realm_access.roles` (see experiment results below).

### Agent-to-Tool Flow

```
Agent ──(JWT in Authorization header)──→ MCP Gateway envoy
  → ext_proc Router (processes MCP routing)
    → Gateway envoy preserves original Authorization header
      → mongodb-mcp (parses JWT, filters by realm_access.roles)
```

How JWT reaches the backend tool:

1. User JWT propagates through A2A chain: Frontend → Campaign API → Campaign Director → Customer Analyst
2. Customer Analyst's `AuthCapture` middleware captures JWT from HTTP request into ContextVar
3. `agent_executor.py` reads ContextVar → passes to `call_mcp_tool(auth_headers=...)`
4. `call_mcp_tool` extracts Bearer token → passes as `auth=token` to fastmcp Client
5. fastmcp sends `Authorization: Bearer <JWT>` on every POST to Gateway
6. Gateway envoy ext_proc Router processes routing (authority, path, session ID) but does NOT strip the Authorization header
7. Gateway envoy forwards request to mongodb-mcp with original Authorization preserved
8. mongodb-mcp parses JWT and applies per-user filtering

Key insight: The Authorization header survives through Gateway ext_proc because Envoy's `HeaderMutation` only modifies explicitly set/removed headers — unmentioned headers are preserved from the original request.

Requirements:
- `AuthCapture` middleware on Customer Analyst (captures JWT from A2A HTTP request)
- `sub` claim present in JWT (openid scope with sub mapper for Keycloak 26+)
- Agent code must pass JWT (fastmcp `auth=token` parameter)
- Istio AuthorizationPolicy restricts direct tool access (only Gateway namespaces allowed)

### Installation

MCP Gateway is installed as part of `infra/kagenti/install.sh` (Phase 4):

```bash
# Chart and version
helm install mcp-gateway oci://ghcr.io/kuadrant/charts/mcp-gateway \
  --version 0.7.0-rc2 \
  --create-namespace -n mcp-system \
  --set "image.tag=v0.7.0-rc2" \
  --set "mcpGatewayExtension.create=true" \
  --set "mcpGatewayExtension.gatewayRef.name=mcp-gateway" \
  --set "mcpGatewayExtension.gatewayRef.namespace=gateway-system" \
  --timeout 5m
```

This creates:
- `mcp-system` namespace with controller + broker pods
- `mcp-gateway` Gateway resource in `gateway-system` (Istio class)
- CRDs: `MCPServerRegistration` (register backend MCP servers), `MCPVirtualServer` (compose tool sets)

### Verification

```bash
# Check pods
oc get pods -n mcp-system

# Check Gateway
oc get gateway -n gateway-system

# Check CRDs
oc get crd | grep mcp

# Check registered servers
oc get mcpservers -A
oc get mcpvirtualservers -A
```

### Registering MCP Servers

To put a tool behind MCP Gateway, create an HTTPRoute + MCPServer:

```yaml
# 1. HTTPRoute: route traffic from Gateway to backend
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mongodb-mcp-route
  namespace: marketing
spec:
  parentRefs:
  - name: mcp-gateway
    namespace: gateway-system
  rules:
  - backendRefs:
    - name: mongodb-mcp
      port: 8082
---
# 2. MCPServer: register with Gateway controller
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPServerRegistration
metadata:
  name: mongodb-mcp
  namespace: marketing
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: mongodb-mcp-route
  path: /mcp
  toolPrefix: mongodb
```

The Gateway controller discovers tools via MCP `tools/list` and federates them through the broker-router. Agents call the Gateway's MCP endpoint instead of individual tools.

### Authorization (via urlElicitation)

AuthPolicy on tool HTTPRoutes is **not used**. MCP Gateway's broker connects to backend tools via its own Router (ext_proc on gRPC :50051), which by default creates new sessions **without forwarding the original user JWT**. We solved this using the `urlElicitation` mechanism.

#### The Problem: Router Cuts JWT Chain

```
Agent ──(JWT)──→ Gateway envoy → Router (ext_proc)
                                    │
                        Router creates new session (NO JWT by default)
                                    │
                                    ▼
                              mongodb-mcp → No user identity → No filtering
```

The Router (`mcp-gateway` pod in mcp-system) runs both a Broker (HTTP :8080) and a Router (gRPC :50051). When routing `tools/call` requests, it creates fresh HTTP connections to backend tools without propagating the original `Authorization` header.

AuthPolicy on tool HTTPRoutes blocks the Router (it has no JWT), and AuthPolicy on the broker route breaks MCP streamable-http (SSE GET requests don't carry JWT → 401 with empty content-type → `Unexpected content type` error in fastmcp Client).

#### The Solution: AuthCapture + ext_proc Header Preservation (Verified 2026-06-02)

The original problem was that mongodb-mcp never received the user's JWT. Root cause analysis traced the break to **Customer Analyst**, not MCP Gateway.

**Root cause**: Customer Analyst's `TraceContextMiddleware` only captured `traceparent`/`tracestate` headers, ignoring `authorization`. The JWT from Campaign Director's A2A call was present in the HTTP request but never extracted by the agent code.

**Fix**: Added `AuthCapture` middleware (`customer-analyst/app/auth.py`) that captures the Authorization header into a ContextVar, matching Campaign Director's existing pattern. The JWT then flows: ContextVar → `agent_executor.py` → `call_mcp_tool(auth_headers=...)` → fastmcp Client `auth=token`.

**How JWT survives through MCP Gateway**: Envoy ext_proc uses `HeaderMutation` to modify routing headers (authority, path, session ID). Headers not explicitly set or removed are preserved from the original request. The Router does NOT remove the `authorization` header — only `x-mcp-authorized` and `x-mcp-virtualserver` are stripped as internal headers.

**MCP Gateway Router source code** (`internal/mcp-router/request_handlers.go`) has additional JWT handling paths that are NOT used in our setup:

- `initializeMCPSeverSession`: forwards headers via `passThroughHeaders` during session creation (hairpin request)
- `tokenURLElicitation`: injects cached user token on every `tools/call` — only when `tokenURLElicitation` is configured on MCPServerRegistration (we don't configure it because fastmcp Client doesn't support the `-32042` elicitation protocol)

**Verified result (2026-06-02)**:

```
# bob (no platinum-access) — get_all_vip_customers
Total: 4 | Tiers: gold(3), diamond(1) | Platinum: 0

# alice (has platinum-access) — get_all_vip_customers
Total: 8 | Tiers: platinum(4), gold(3), diamond(1)
```

mongodb-mcp logs:
```
bob lacks 'platinum-access' role/scope — filtering out platinum members
alice has 'platinum-access' role (realm_access) — full access
```

#### Key Findings

- **JWT break was at Customer Analyst, not MCP Gateway**: The A2A HTTP request carried the Authorization header, but `TraceContextMiddleware` didn't capture it. Fix: dedicated `AuthCapture` middleware
- **ext_proc preserves original Authorization**: Gateway envoy's ext_proc only modifies routing headers — the original `authorization` header passes through to the backend unchanged
- **Campaign API has its own role check**: `_check_role_audience_restriction()` rejects platinum-targeting campaigns for users without `platinum-access` at the API level — a separate protection layer from mongodb-mcp's data filtering
- **ALLOW_JWT_FALLBACK=false blocks Inspector/kagenti UI**: These paths don't carry user JWT, so `false` returns "Access denied". Set `true` for debugging, `false` for production
- **kagenti UI and MCP Inspector** do not pass user JWT to MCP Gateway — per-user filtering only works through the agent code path (fastmcp Client with `auth=token`)

Per-user authorization is handled by `mongodb-mcp/app/server.py` → `filter_customers_by_user_perm()`, which reads JWT `realm_access.roles` from the forwarded Authorization header. Alice (has `platinum-access`) sees all customers; Bob (no `platinum-access`) has platinum customers filtered out.

### Access Control (Implemented)

Istio AuthorizationPolicy restricts direct access to tools:

```yaml
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: mongodb-mcp-gateway-only
spec:
  selector:
    matchLabels:
      app: mongodb-mcp
  action: ALLOW
  rules:
  - from:
    - source:
        namespaces: ["gateway-system", "mcp-system", "kagenti-system"]
```

Kubernetes NetworkPolicy is NOT used — Istio ambient mesh ztunnel interferes with kubelet health probes. Istio AuthorizationPolicy operates at L7 and does not affect probes.

### JWT Fallback Switch

mongodb-mcp has an `ALLOW_JWT_FALLBACK` setting (default `false` in code, configured via k8s.yaml):

- `false` (production): when no JWT is present (e.g. calls from MCP Inspector, kagenti UI Tool Catalog), returns `Access denied: missing authorization headers`. Secure but blocks admin tool debugging.
- `true` (current): falls back to parsing JWT from Authorization header. When no JWT at all, returns unfiltered data — **insecure for production**, allows unauthenticated access to all data through Gateway broker.

**Note**: The deployed mongodb-mcp image must include the `ALLOW_JWT_FALLBACK` field in `settings.py`. Older images without this field ignore the env var and always return unfiltered data when no JWT is present.

### MCP Inspector

Inspector v0.21.1 supports native MCP OAuth (Guided OAuth Flow + PKCE). install.sh configures:

1. `DANGEROUSLY_OMIT_AUTH=true` kept (chart default) — skips proxy session token, reduces friction
2. `mcp-inspector` Keycloak client (public, PKCE) — pre-registered to skip DCR
3. Anonymous DCR enabled on Keycloak — removes trusted-hosts policy
4. `oauthProtectedResource` on MCPGatewayExtension — broker serves `/.well-known/oauth-protected-resource`
5. AuthPolicy on broker route — **disabled** (MCP streamable-http GET requests don't carry JWT, causing empty content-type 401 responses)

**Note**: MCP Inspector and kagenti UI Tool Catalog connect to MCP Gateway without user JWT. Per-user filtering does not apply through these paths — they return unfiltered data (or Access denied if `ALLOW_JWT_FALLBACK=false`).

Setup (one-time, localStorage remembers):

| Step | Action |
|------|--------|
| 1 | URL: `https://mcp-gateway-gateway-system.apps.<DOMAIN>/mcp` (external) |
| 2 | Connection Type: Via Proxy |
| 3 | Inspector Proxy Address: `https://mcp-proxy-kagenti-system.apps.<DOMAIN>` |
| 4 | Authentication → Guided OAuth Flow → Client ID: `mcp-inspector` → Continue |
| 5 | Keycloak login → token auto-acquired |
| 6 | Back to Connect → Connect → Tools → Run Tool |

**Known issue**: kagenti UI (MCP Gateway page) constructs the Inspector URL with an internal `serverUrl` (`mcp-gateway-istio.gateway-system.svc.cluster.local`). This is hardcoded in the kagenti-ui frontend JS bundle. After opening Inspector from kagenti UI, manually change the URL to the external address, or open Inspector directly with the external URL.

## Zero Trust Maturity Assessment

| Principle | Status | Notes |
|-----------|--------|-------|
| Transport encryption (mTLS) | ✅ Done | Istio ambient mesh — ztunnel auto mTLS |
| Workload identity | ✅ Done | SPIRE SPIFFE SVIDs per pod |
| User authentication | ✅ Done | Keycloak SSO + PKCE + JWT |
| Inbound validation | ✅ Done | AuthBridge validates JWT signature/issuer/audience |
| User-level authorization | ✅ Done | `realm_access.roles` propagated (platinum-access filtering) |
| Tool access control | ✅ Done | MCP Gateway AuthPolicy + Istio AuthorizationPolicy |
| Service-to-service delegation | ❌ Gap | JWT passthrough — no per-hop caller identity |
| Least privilege per agent | ❌ Gap | Every agent receives full user JWT |
| Audit chain | ❌ Gap | No nested `act` claims — call chain not traceable |

### What's Missing and Why We Can't Fix It Now

**1. Service-to-service delegation identity**

Currently Agent A forwards the user's JWT unchanged to Agent B. Agent B cannot verify "was this called by Agent A or by someone else with the same JWT?" True zero trust requires each hop to carry the caller's identity.

```
Current:  User JWT → Agent A → (same User JWT) → Agent B
Target:   User JWT → Agent A → (Agent A SPIFFE + nested act{user}) → Agent B
```

**Why not now**: AuthBridge supports outbound token exchange (audience-scoped), but does not implement nested `act` claims. Keycloak's standard token exchange [also lacks delegation semantics](https://github.com/keycloak/keycloak/discussions/43108). The Red Hat ET [zero-trust-agent-demo](https://github.com/redhat-et/zero-trust-agent-demo) demonstrates this with a custom credential-gateway + OPA, but this is not integrated into kagenti AuthBridge yet.

**2. Least privilege per agent**

creative-producer (only needs to generate HTML) and customer-analyst (needs customer data) both receive the same full user JWT. creative-producer could theoretically access customer data endpoints.

**Why not now**: Requires a permission intersection engine to scope each agent's effective permissions. The zero-trust-agent-demo uses OPA for this, but it's a standalone component not part of kagenti. Without delegation identity (gap #1), there is no token-level mechanism to restrict what an agent can do independently of the user's roles. Istio AuthorizationPolicy provides namespace-level isolation (tools only accept traffic from gateway-system), but not per-agent capability scoping.

**3. Keycloak token exchange and roles (verified)**

Keycloak's [standard token exchange](https://www.keycloak.org/2025/05/standard-token-exchange-kc-26-2) (26.2+) does not execute `oidc-usermodel-realm-role-mapper` during the exchange grant type. We verified this end-to-end: created a `mcp-gateway` target client with the `roles` scope (containing the realm role mapper) correctly assigned, performed a successful token exchange — the exchanged token had `preferred_username: alice` but `realm_access.roles` was empty. This is Keycloak behavior, not a scope configuration issue.

**Why not now**: `realm_access.roles` cannot be preserved through standard token exchange regardless of configuration. JWT passthrough is the only way to maintain per-user role-based authorization (alice's `platinum-access` vs bob's lack thereof).

### Current Approach is Correct

JWT passthrough + application-level `filter_customers_by_user_perm()` is the practical interim solution. The path to full zero trust requires three things to converge:

1. Keycloak executes realm role mappers during token exchange (or supports `act` claims with role delegation)
2. Kagenti AuthBridge integrates nested `act` claims into outbound exchange
3. A permission intersection engine (OPA or similar) is integrated into the platform

Until then, JWT passthrough preserves user identity and roles at every hop, which is the approach used by kagenti's own demos and documentation.

## Operational: Cluster Reboot Recovery

Istio ambient mesh uses ztunnel (DaemonSet) with in-pod traffic redirection. After cluster/node reboot, CRI-O restores pod sandboxes without re-invoking the CNI plugin chain, so ztunnel's in-pod sockets (ports 15001/15006/15008) are lost. This is a [known upstream issue](https://github.com/istio/istio/issues/57285).

**Symptoms**: `connection reset by peer`, `connection refused`, 503/504 across namespaces, `proxy-init` `Init:CrashLoopBackOff` (iptables kernel module not loaded yet).

**Recovery**: Run `./post-reboot.sh` which:
1. Waits for ztunnel DaemonSet to be fully Ready
2. Restarts pods stuck in `Init:CrashLoopBackOff` (proxy-init iptables failure)
3. Detects pods missing ztunnel socket via `/proc/net/tcp` and restarts their owners
4. Restarts Gateway envoy (`gateway-system`) and MCP Gateway broker (`mcp-system`)

**Automated recovery**: `infra/kagenti/ambient-reconciler.yaml` is a CronJob (every 3 min) that performs the same ztunnel socket detection and pod restart. Deploy with `oc apply -f infra/kagenti/ambient-reconciler.yaml`.

**AuthBridge mode**: We use `envoy-sidecar` (iptables-based, advanced). Kagenti default is `proxy-sidecar` (HTTP_PROXY-based). The HBONE breakage is a ztunnel issue unrelated to AuthBridge mode — pods without AuthBridge are equally affected.

## References

- [Zero trust for AI agents: why delegation beats impersonation](https://next.redhat.com/2026/05/21/zero-trust-for-ai-agents-why-delegation-beats-impersonation/) — Red Hat Emerging Technologies, May 2026
- [Zero trust agent demo](https://github.com/redhat-et/zero-trust-agent-demo) — Permission intersection prototype with OPA + SPIFFE
- [Keycloak token exchange delegation discussion](https://github.com/keycloak/keycloak/discussions/43108) — `act` claim support status
- [Keycloak Standard Token Exchange (26.2)](https://www.keycloak.org/2025/05/standard-token-exchange-kc-26-2) — RFC 8693 support
- [Keycloak JWT Authorization Grant (RFC 7523)](https://www.keycloak.org/2026/01/jwt-authorization-grant) — Keycloak 26.5
- [Kagenti GitHub](https://github.com/kagenti/kagenti)
- [MCP Gateway — Kuadrant](https://github.com/Kuadrant/mcp-gateway)
- [Per-user OAuth token management — kagenti #1164](https://github.com/kagenti/kagenti/issues/1164)
