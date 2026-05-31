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

### Why We Use JWT Passthrough

We disabled AuthBridge outbound token exchange (`authproxy-routes` not configured) because:

1. **Roles may be lost**: Keycloak's standard token exchange filters client scopes based on the target audience. If the target client's scope configuration doesn't include realm role mappers, `realm_access.roles` can be stripped. This is a configuration challenge — not an absolute limitation — but requires careful per-client scope setup that is fragile across upgrades.

2. **No delegation identity**: AuthBridge's current token exchange replaces the user JWT with an audience-scoped token. The exchanged token identifies the **agent** (via SPIFFE), not the **user who delegated**. Without nested `act` claims, per-user authorization (alice vs bob) cannot be enforced downstream.

3. **No permission intersection engine**: Even if tokens carried delegation context, there is no policy engine (OPA or otherwise) integrated into kagenti to compute permission intersections at each hop.

JWT passthrough preserves the original user JWT (with `realm_access.roles`) at every hop. Combined with application-level `filter_customers_by_user_perm()`, this is the correct interim approach until kagenti integrates delegation into AuthBridge.

## MCP Gateway for Tools

### Architecture (v0.7.0-rc2)

MCP Gateway v0.7.0 introduced `MCPGatewayExtension` which auto-creates:
- `mcp-gateway-route` HTTPRoute → routes `/mcp` to the broker
- EnvoyFilter → ext_proc for MCP protocol parsing and tool call routing

Agents connect to the Gateway envoy (`mcp-gateway-istio.gateway-system.svc:8080/mcp`). The ext_proc router parses `tools/call` requests and routes them to the correct backend MCP server via Istio.

**Current usage**: Agents call tools through Gateway (`mcp-gateway-istio.gateway-system.svc:8080/mcp`). MCP Inspector browses tools via broker. Agent code defaults to `localhost` for local dev; k8s.yaml overrides point to the Gateway address.

### Agent-to-Tool Flow

```
Agent → (JWT passthrough) → MCP Gateway → Tool
                               ↓
                        1. Validate JWT (roles intact)
                        2. Tool-level ACL (CEL expressions)
                        3. Inject x-user-roles header
                        4. Forward to tool backend
```

Advantages over authproxy-routes:
- No token exchange needed → roles preserved
- Tool-level ACL via `resource_access` JWT claim
- Header injection for downstream data filtering
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

### Authorization (Partially Implemented)

AuthPolicy on mongodb-mcp's HTTPRoute validates JWT and injects `x-user-roles` header. imagegen-mcp does not have an AuthPolicy (image generation does not require per-user filtering).

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: mongodb-mcp-auth
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: mongodb-mcp-route
  rules:
    authentication:
      keycloak-jwt:
        jwt:
          issuerUrl: https://<KEYCLOAK_ROUTE>/realms/kagenti
    response:
      success:
        headers:
          x-user-roles:
            plain:
              expression: "auth.identity.realm_access.roles.join(',')"
```

Requires Kuadrant CR (`kuadrant.io/v1beta1`) to enable policy enforcement.

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

mongodb-mcp has an `ALLOW_JWT_FALLBACK` setting (default `false`):
- `false` (production): requires `x-user-roles` header from Gateway AuthPolicy; rejects requests without it
- `true` (local dev): falls back to parsing JWT from Authorization header (unverified signature)

### MCP Inspector

Inspector v0.21.1 supports native MCP OAuth (Guided OAuth Flow + PKCE). install.sh configures:

1. `DANGEROUSLY_OMIT_AUTH=true` kept (chart default) — skips proxy session token, reduces friction
2. `mcp-inspector` Keycloak client (public, PKCE) — pre-registered to skip DCR
3. Anonymous DCR enabled on Keycloak — removes trusted-hosts policy
4. `oauthProtectedResource` on MCPGatewayExtension — broker serves `/.well-known/oauth-protected-resource`
5. AuthPolicy on broker route — returns 401 to trigger OAuth discovery

Security is enforced by MCP Gateway AuthPolicy (JWT required for all tool calls). The proxy session token adds friction without meaningful protection on top of OAuth + Keycloak.

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

**3. Keycloak token exchange and roles**

Keycloak's [standard token exchange](https://www.keycloak.org/2025/05/standard-token-exchange-kc-26-2) (26.2+) performs client scope filtering based on the target audience. If the target client's scope doesn't include realm role mappers, `realm_access.roles` may be stripped from the exchanged token. This is a configuration challenge rather than an absolute limitation — but requires careful per-client scope setup.

**Why not now**: Correct scope configuration could preserve realm roles in exchanged tokens, but AuthBridge's outbound exchange still replaces the user identity with the agent's SPIFFE identity. Even with roles preserved, there's no `act` claim to indicate "this agent is acting on behalf of alice" — the downstream service sees the agent, not the user. JWT passthrough sidesteps both issues by keeping the original user token intact.

### Current Approach is Correct

JWT passthrough + application-level `filter_customers_by_user_perm()` is the practical interim solution. The path to full zero trust requires three things to converge:
1. Keycloak supports delegation semantics (`act` claims) in token exchange
2. Kagenti AuthBridge integrates nested `act` claims into outbound exchange
3. A permission intersection engine (OPA or similar) is integrated into the platform

Until then, JWT passthrough preserves user identity and roles at every hop, which is the approach used by kagenti's own demos and documentation.

## References

- [Zero trust for AI agents: why delegation beats impersonation](https://next.redhat.com/2026/05/21/zero-trust-for-ai-agents-why-delegation-beats-impersonation/) — Red Hat Emerging Technologies, May 2026
- [Zero trust agent demo](https://github.com/redhat-et/zero-trust-agent-demo) — Permission intersection prototype with OPA + SPIFFE
- [Keycloak token exchange delegation discussion](https://github.com/keycloak/keycloak/discussions/43108) — `act` claim support status
- [Keycloak Standard Token Exchange (26.2)](https://www.keycloak.org/2025/05/standard-token-exchange-kc-26-2) — RFC 8693 support
- [Keycloak JWT Authorization Grant (RFC 7523)](https://www.keycloak.org/2026/01/jwt-authorization-grant) — Keycloak 26.5
- [Kagenti GitHub](https://github.com/kagenti/kagenti)
- [MCP Gateway — Kuadrant](https://github.com/Kuadrant/mcp-gateway)
- [Per-user OAuth token management — kagenti #1164](https://github.com/kagenti/kagenti/issues/1164)
