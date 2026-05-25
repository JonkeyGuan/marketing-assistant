# Kagenti Platform Installation

Install the [Kagenti](https://github.com/kagenti/kagenti) AI agent platform on OpenShift.

## Components

| Component | Description |
|-----------|-------------|
| **Keycloak** | Identity and access management (RHBK Operator + PostgreSQL) |
| **MLflow** | ML experiment and trace tracking with OIDC auth |
| **Istio Ambient** | Service mesh (ambient mode, ztunnel) |
| **SPIRE** | SPIFFE-based workload identity |
| **Kiali** | Service mesh observability dashboard |
| **OTEL Collector** | OpenTelemetry trace collection |
| **cert-manager** | TLS certificate management |
| **MCP Gateway** | Model Context Protocol gateway for agent tools |
| **Kagenti** | Agent operator, web UI, AuthBridge |

## Prerequisites

- OpenShift 4.19+ cluster with `cluster-admin` access
- `oc` CLI logged in
- `helm` 3.x installed
- `python3` with `pyyaml` module (for hook processing)
- Pre-existing OSSM (OpenShift Service Mesh) is supported — the script syncs Istio CA automatically

## Install

```bash
./install.sh
```

The script auto-detects the cluster domain from OpenShift. To override:

```bash
DOMAIN=apps.cluster-xxx.sandbox.opentlc.com ./install.sh
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN` | auto-detected | OpenShift apps domain |
| `CHART_VERSION` | `0.6.0-rc.6` | kagenti / kagenti-deps Helm chart version |
| `MCP_GW_VERSION` | `0.4.1` | MCP Gateway chart and image version |

### What the Script Does

| Phase | Description |
|-------|-------------|
| **0 — Pre-flight** | Adopt existing istio-system/gateway-system namespaces for Helm, enable OVN `routingViaHost` for Istio Ambient |
| **1 — kagenti-deps** | Install Helm chart with `--no-hooks` (Keycloak, MLflow, Istio, OTEL, SPIRE, Kiali, cert-manager) |
| **2 — Wait** | Wait for operators (cert-manager, RHBK, Keycloak CRD, PostgreSQL), grant SPIRE privileged SCC |
| **3 — Hooks** | Apply operand CRs (Keycloak CR, Istio CR, Kiali CR) via Python YAML parser, sync Istio CA for OSSM coexistence |
| **3b — MCP Gateway** | Install MCP Gateway Helm chart with pinned image tag |
| **4 — kagenti** | Install kagenti Helm chart with `--no-hooks`, set SPIFFE prefix and OAuth config |
| **4b — Hooks** | Apply kagenti hook resources, create `kagenti-ui-config` ConfigMap with route URLs |
| **4c — Fixups** | Patch Kiali URL, MLflow OIDC/probes/PVC, AuthBridge config (replace `localtest.me` defaults) |
| **4d — Users** | Create unified `admin` user in master + kagenti realms, delete test users, create `keycloak-admin` secret |
| **5 — Verify** | Print pod status and route URLs |

## Uninstall

```bash
./uninstall.sh
```

Removes kagenti, MCP Gateway, and kagenti-deps Helm releases, then cleans up cluster-scoped resources (ClusterRoles, webhooks, SCCs) and Istio/SPIRE operand CRs. Prompts for confirmation before proceeding.

## Customization

Edit the values files before installation:

| File | Purpose |
|------|---------|
| `values-deps.yaml` | Toggle dependencies (Keycloak, MLflow, Istio, Kiali, etc.), set credentials |
| `values-kagenti.yaml` | Configure agent namespaces, UI auth, MLflow auth, SPIFFE/OAuth settings |

### Key Overrides

```bash
# Change chart version
CHART_VERSION=0.6.0 ./install.sh

# Set OpenAI API key for agents
helm upgrade kagenti ... --set secrets.openaiApiKey=sk-xxx

# Add more agent namespaces
helm upgrade kagenti ... --set agentNamespaces='{marketing,staging}'
```

## Post-Install Credentials

After installation, the `admin` user credentials are stored in:

- `keycloak-admin` secret in the `keycloak` namespace
- `keycloak-admin-secret` secret in the `kagenti-system` namespace

```bash
# Retrieve admin password
oc get secret keycloak-admin -n keycloak -o go-template='{{.data.password | base64decode}}'
```

## Verification

```bash
# Check all pods
oc get pods -n kagenti-system
oc get pods -n keycloak
oc get pods -n mcp-system
oc get pods -n istio-system

# Check routes
oc get routes -n kagenti-system
oc get routes -n keycloak
oc get route kiali -n istio-system

# Check UI config
oc get configmap kagenti-ui-config -n kagenti-system -o yaml
```

## OpenShift-Specific Notes

- **OVN routingViaHost**: Automatically patched to `true` for Istio Ambient mesh compatibility
- **SPIRE SCC**: `spire-agent` and `spire-spiffe-csi-driver` are granted privileged SCC
- **OSSM Coexistence**: If OpenShift Service Mesh is pre-installed, the script copies `istio-ca-secret` from `openshift-ingress` to `istio-system` and restarts istiod/ztunnel to avoid CA mismatch
- **Kiali Auth**: Uses OpenShift OAuth (not Keycloak) — login with OpenShift credentials
- **Helm --no-hooks**: Both charts are installed with `--no-hooks`; hook resources (operand CRs) are extracted and applied manually via Python to avoid ordering issues

## References

- [Kagenti GitHub](https://github.com/kagenti/kagenti)
- [kagenti-deps values.yaml](https://github.com/kagenti/kagenti/blob/main/charts/kagenti-deps/values.yaml)
- [kagenti values.yaml](https://github.com/kagenti/kagenti/blob/main/charts/kagenti/values.yaml)
- [OCP setup script](https://github.com/kagenti/kagenti/blob/main/scripts/ocp/setup-kagenti.sh)
