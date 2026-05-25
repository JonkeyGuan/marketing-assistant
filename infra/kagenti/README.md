# Kagenti Platform Installation

Install the [Kagenti](https://github.com/kagenti/kagenti) AI agent platform on OpenShift, including:

- **Keycloak** — Identity and access management (RHBK Operator)
- **MLflow** — ML experiment and trace tracking
- **Kagenti** — Agent operator, UI, MCP gateway

## Prerequisites

- OpenShift 4.19+ cluster with `cluster-admin` access
- `oc` CLI logged in
- `helm` 3.x installed

## Install

```bash
# Auto-detects cluster domain from OpenShift
./install.sh

# Or specify domain manually
DOMAIN=apps.<OpenShift Doamin> ./install.sh
```

The script runs in two phases:
1. **kagenti-deps** — Installs Keycloak (RHBK Operator + PostgreSQL), MLflow, Istio, cert-manager, OTEL collector, SPIRE
2. **kagenti** — Installs the agent operator, web UI, and MCP gateway

## Uninstall

```bash
./uninstall.sh
```

## Customization

Edit the values files before installation:

| File | Purpose |
|------|---------|
| `values-deps.yaml` | Toggle dependencies (Keycloak, MLflow, Istio, etc.), set credentials |
| `values-kagenti.yaml` | Configure agent namespaces, UI auth, MLflow auth |

### Common overrides

```bash
# Change Keycloak admin password
helm upgrade kagenti-deps ... --set keycloak.auth.adminPassword=my-password

# Set OpenAI API key for agents
helm upgrade kagenti ... --set secrets.openaiApiKey=sk-xxx

# Add more agent namespaces
helm upgrade kagenti ... --set agentNamespaces='{marketing,staging}'
```

## Verification

```bash
oc get pods -n kagenti-system
oc get pods -n keycloak
oc get routes -n kagenti-system
oc get routes -n keycloak
```

## References

- [Kagenti GitHub](https://github.com/kagenti/kagenti)
- [kagenti-deps values.yaml](https://github.com/kagenti/kagenti/blob/main/charts/kagenti-deps/values.yaml)
- [kagenti values.yaml](https://github.com/kagenti/kagenti/blob/main/charts/kagenti/values.yaml)
- [OCP setup script](https://github.com/kagenti/kagenti/blob/main/scripts/ocp/setup-kagenti.sh)
