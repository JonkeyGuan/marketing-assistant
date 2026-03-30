# Coder Agent

A2A (Agent-to-Agent) microservice that generates HTML/CSS/JS marketing landing pages for luxury casino campaigns.

Part of the [Marketing Assistant](../README.md) multi-agent system. Runs as a standalone service, communicates with the orchestrator via the [Google A2A protocol](https://github.com/a2aproject/a2a-python).

## Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenAI-compatible LLM endpoint and API key

## Project Structure

```
coder-agent/
  app/
    __init__.py
    __main__.py                  # Entry point: assembles & starts A2A server
    executor.py                  # AgentExecutor: handles A2A task lifecycle
    generate_html.py             # Core skill: LLM-powered HTML generation
    settings.py                  # Environment-based configuration
  k8s/                           # OpenShift deployment manifests
  Containerfile
  pyproject.toml
```

## Local Development

```bash
cp .env.example .env            # edit with your model endpoint & token
uv sync
uv run app
```

Verify:

```bash
curl http://localhost:8001/.well-known/agent.json
```

## Build & Deploy to OpenShift

### 1. Build & push image

```bash
./build.sh          # default: latest
./build.sh v1.0.0   # or with a specific tag
```

### 2. Create Secret

```bash
NAMESPACE=0-marketing-assistant-demo

oc create secret generic coder-agent-secrets \
  --from-literal=MODEL_TOKEN=<your-token> \
  -n $NAMESPACE --dry-run=client -o yaml | oc apply -f -
```

### 3. Apply manifests

```bash
oc apply -f k8s/ -n $NAMESPACE
oc rollout status deployment/coder-agent -n $NAMESPACE
```

### 4. Verify

```bash
# External
ROUTE=$(oc get route coder-agent -n $NAMESPACE -o jsonpath='{.spec.host}')
curl https://$ROUTE/.well-known/agent.json

# In-cluster URL (for orchestrator configmap)
# http://coder-agent.${NAMESPACE}.svc.cluster.local:8001
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `MODEL_ENDPOINT` | LLM API endpoint (OpenAI-compatible) | — |
| `MODEL_NAME` | Model name | — |
| `MODEL_TOKEN` | API bearer token | — |
| `CODER_A2A_PORT` | Server listen port | `8001` |

## A2A Interface

**Skill:** `generate_html`

**Input** (via `DataPart`):
```json
{
  "campaign_name": "Chinese New Year VIP Bonus",
  "campaign_description": "50% deposit bonus for VIP members",
  "hotel_name": "Grand Luxe Hotel & Casino",
  "theme_colors": {"primary": "#C41E3A", "secondary": "#D4AF37", ...},
  "theme_name": "Festive Red",
  "start_date": "January 25, 2026",
  "end_date": "February 10, 2026"
}
```

**Output** (artifact): Generated single-page HTML with embedded CSS/JS.

## Architecture

```
Orchestrator ──A2A──▶ Coder Agent ──HTTP──▶ Code LLM (configurable)
                      (this service)
```

The orchestrator sends campaign parameters via A2A `tasks/send`. This agent calls the code LLM to generate a complete landing page, then returns the HTML as a task artifact.
