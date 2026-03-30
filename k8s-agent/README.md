# K8s Agent

A2A (Agent-to-Agent) microservice that deploys marketing campaign pages to OpenShift (preview and production).

Part of the [Marketing Assistant](../README.md) multi-agent system. Runs as a standalone service, communicates with the orchestrator via the [Google A2A protocol](https://github.com/a2aproject/a2a-python).

## Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenShift cluster (via kubeconfig or in-cluster)

## Project Structure

```
k8s-agent/
  app/
    __init__.py
    __main__.py                  # Entry point: assembles & starts A2A server
    executor.py                  # AgentExecutor: handles A2A task lifecycle
    deploy.py                    # Core skill: deploy HTML to OpenShift
    settings.py                  # Environment-based configuration
  k8s/                           # OpenShift deployment manifests
  Containerfile
  pyproject.toml
```

## Local Development

```bash
cp .env.example .env            # edit with your cluster domain & namespaces
uv sync
uv run app
```

Verify:

```bash
curl http://localhost:8004/.well-known/agent.json
```

## Build & Deploy to OpenShift

### 1. Build & push image

```bash
./build.sh          # default: latest
./build.sh v1.0.0   # or with a specific tag
```

### 2. Apply manifests

```bash
NAMESPACE=0-marketing-assistant-demo

oc apply -f k8s/ -n $NAMESPACE
oc rollout status deployment/k8s-agent -n $NAMESPACE
```

### 3. Verify

```bash
# External
ROUTE=$(oc get route k8s-agent -n $NAMESPACE -o jsonpath='{.spec.host}')
curl https://$ROUTE/.well-known/agent.json

# In-cluster URL (for orchestrator configmap)
# http://k8s-agent.${NAMESPACE}.svc.cluster.local:8004
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `CLUSTER_DOMAIN` | OpenShift cluster apps domain | — |
| `DEV_NAMESPACE` | Dev namespace for preview deployments | — |
| `PROD_NAMESPACE` | Production namespace | — |
| `K8S_A2A_PORT` | Server listen port | `8004` |

## A2A Interface

**Skills:** `deploy_preview`, `promote_production`

**Input** (via `DataPart`):
```json
{
  "action": "deploy_preview",
  "campaign_id": "cny-2026-vip-bonus",
  "generated_html": "<!DOCTYPE html>..."
}
```

**Output** (artifact — deploy_preview):
```json
{
  "deployment_name": "cny-2026-vip-bonus-preview",
  "preview_url": "https://cny-2026-vip-bonus-preview-dev.apps.cluster.example.com",
  "preview_qr_code": "data:image/png;base64,..."
}
```

**Output** (artifact — promote_production):
```json
{
  "deployment_name": "cny-2026-vip-bonus",
  "production_url": "https://cny-2026-vip-bonus-prod.apps.cluster.example.com"
}
```

## Architecture

```
Orchestrator ──A2A──> K8s Agent ──K8s API──> OpenShift Cluster
                      (this service)         (dev & prod namespaces)
```

The orchestrator sends campaign HTML and action via A2A `tasks/send`. This agent deploys the HTML as an nginx pod to OpenShift and returns the route URL.
