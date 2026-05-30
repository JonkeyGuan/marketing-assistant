# Zero Trust Authentication Architecture

How AuthBridge, SPIFFE, and token exchange secure agent-to-agent and agent-to-tool communication in this project.

## Overview

Kagenti AuthBridge injects zero-trust authentication into every agent at deploy time via 3 sidecars (envoy-proxy, spiffe-helper, config-reloader). Agent code is auth-unaware — all validation happens at the infrastructure layer.

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

| Component | Role |
|-----------|------|
| `envoy-proxy` | Sidecar proxy — inbound JWT validation, outbound token exchange (if configured) |
| `spiffe-helper` | Obtains SPIFFE SVID from SPIRE, writes JWT-SVID to `/opt/jwt_svid.token` |
| `config-reloader` | Watches ConfigMap changes, signals envoy to reload |
| `authbridge-config` | ConfigMap — ISSUER, EXPECTED_AUDIENCE, KEYCLOAK_URL |
| `spiffe-helper-config` | ConfigMap — SPIRE agent socket, jwt_audience (must match Keycloak issuer URL) |
| `authproxy-routes` | ConfigMap (optional) — outbound token exchange routes |

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

## Future: Delegation Model (Planned by Kagenti)

Kagenti is developing a **permission intersection** model that solves the token exchange limitation:

### Nested `act` Claims

Instead of losing user permissions, the exchanged token **nests** the original user's identity and permissions:

```json
{
  "sub": "spiffe://cluster/ns/marketing/sa/creative-producer",
  "capabilities": ["image-generation", "content-creation"],
  "act": {
    "sub": "alice",
    "roles": ["platinum-access", "admin"]
  }
}
```

Multi-hop delegation chains nest further:

```json
{
  "sub": "agent-C",
  "act": {
    "sub": "agent-B",
    "act": {
      "sub": "alice",
      "roles": ["platinum-access"]
    }
  }
}
```

### Permission Intersection

```
Effective Permissions = User Permissions ∩ Agent Capabilities
```

- Alice has `[platinum-access, admin]`
- Agent configured with capabilities `[platinum-access]`
- Effective: `[platinum-access]` — agent can only **reduce** permissions, never expand

### What This Means for Us

When implemented, AuthBridge will:
1. Exchange tokens with nested `act` claims (user roles preserved)
2. Policy engine (OPA/Rego) computes permission intersection at each hop
3. Agent code remains auth-unaware — no application changes needed
4. Full audit trail via nested `act` chain

Our current JWT passthrough + `filter_customers_by_user_perm()` approach is the correct interim solution. When kagenti ships nested `act` claims, the authorization logic moves entirely to the infrastructure layer.

## MCP Gateway for Tools

### Architecture (v0.6.0)

MCP Gateway v0.6.0 introduced `MCPGatewayExtension` which auto-creates:
- `mcp-gateway-route` HTTPRoute → routes `/mcp` to the broker
- EnvoyFilter → ext_proc for MCP protocol parsing and tool call routing

Agents connect to the Gateway envoy (`mcp-gateway-istio.gateway-system.svc:8080/mcp`). The ext_proc router parses `tools/call` requests and routes them to the correct backend MCP server via Istio.

**Current usage**: Agents call tools through Gateway. MCP Inspector browses tools via broker.

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
- NetworkPolicy prevents bypassing the gateway

### Installation

MCP Gateway is installed as part of `infra/kagenti/install.sh` (Phase 4):

```bash
# Chart and version
helm install mcp-gateway oci://ghcr.io/kuadrant/charts/mcp-gateway \
  --version 0.6.0 \
  --create-namespace -n mcp-system \
  --set "image.tag=v0.6.0" \
  --set "mcpGatewayExtension.create=true" \
  --set "mcpGatewayExtension.gatewayRef.name=mcp-gateway" \
  --set "mcpGatewayExtension.gatewayRef.namespace=gateway-system" \
  --timeout 5m
```

This creates:
- `mcp-system` namespace with controller + broker pods
- `mcp-gateway` Gateway resource in `gateway-system` (Istio class)
- CRDs: `MCPServer` (register backend MCP servers), `MCPVirtualServer` (compose tool sets)

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
apiVersion: mcp.kagenti.com/v1alpha1
kind: MCPServer
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

### Authorization (Planned)

Tool-level ACL via Kuadrant AuthPolicy + CEL expressions:

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: mcp-tool-acl
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: mcp-gateway
  rules:
    authorization:
      tool-access:
        cel:
          expression: >
            request.path.endsWith('/tools/call') &&
            'mongodb-full-access' in auth.identity.resource_access.mongodb.roles
    response:
      success:
        headers:
          x-user-roles:
            cel:
              expression: "auth.identity.realm_access.roles.join(',')"
```

See [MCP Gateway — Kuadrant](https://github.com/Kuadrant/mcp-gateway) for details.

## References

- [Zero trust for AI agents: why delegation beats impersonation](https://next.redhat.com/2026/05/21/zero-trust-for-ai-agents-why-delegation-beats-impersonation/) — Red Hat Emerging Technologies, May 2026
- [Kagenti GitHub](https://github.com/kagenti/kagenti)
- [Keycloak JWT Authorization Grant (RFC 7523)](https://www.keycloak.org/2026/01/jwt-authorization-grant) — Keycloak 26.5
- [MCP Gateway — Kuadrant](https://github.com/Kuadrant/mcp-gateway)
- [Per-user OAuth token management — kagenti #1164](https://github.com/kagenti/kagenti/issues/1164)
