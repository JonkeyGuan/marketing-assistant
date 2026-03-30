# Marketing Agent

A2A (Agent-to-Agent) microservice that generates bilingual (EN/中文) marketing email content for luxury casino campaigns.

Part of the [Marketing Assistant](../README.md) multi-agent system. Runs as a standalone service, communicates with the orchestrator via the [Google A2A protocol](https://github.com/a2aproject/a2a-python).

## Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenAI-compatible LLM endpoint and API key

## Project Structure

```
marketing-agent/
  app/
    __init__.py
    __main__.py                  # Entry point: assembles & starts A2A server
    executor.py                  # AgentExecutor: handles A2A task lifecycle
    generate_email.py            # Core skill: LLM-powered email generation
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
curl http://localhost:8003/.well-known/agent.json
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

oc create secret generic marketing-agent-secrets \
  --from-literal=MODEL_TOKEN=<your-token> \
  -n $NAMESPACE --dry-run=client -o yaml | oc apply -f -
```

### 3. Apply manifests

```bash
oc apply -f k8s/ -n $NAMESPACE
oc rollout status deployment/marketing-agent -n $NAMESPACE
```

### 4. Verify

```bash
# External
ROUTE=$(oc get route marketing-agent -n $NAMESPACE -o jsonpath='{.spec.host}')
curl https://$ROUTE/.well-known/agent.json

# In-cluster URL (for orchestrator configmap)
# http://marketing-agent.${NAMESPACE}.svc.cluster.local:8003
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `MODEL_ENDPOINT` | LLM API endpoint (OpenAI-compatible) | — |
| `MODEL_NAME` | Model name | — |
| `MODEL_TOKEN` | API bearer token | — |
| `MARKETING_A2A_PORT` | Server listen port | `8003` |

## A2A Interface

**Skill:** `generate_email`

**Input** (via `DataPart`):
```json
{
  "campaign_name": "Chinese New Year VIP Bonus",
  "campaign_description": "50% deposit bonus for VIP members",
  "hotel_name": "Grand Luxe Hotel & Casino",
  "campaign_url": "https://cny-promo.grandluxe.casino",
  "target_audience": "VIP platinum members",
  "start_date": "January 25, 2026",
  "end_date": "February 10, 2026"
}
```

**Output** (artifact):
```json
{
  "subject_en": "Exclusive CNY Bonus Awaits You",
  "body_en": "<h1>Dear {{customer_name}}</h1>...",
  "subject_zh": "新春贵宾专享礼遇",
  "body_zh": "<h1>尊敬的 {{customer_name}}</h1>..."
}
```

## Architecture

```
Orchestrator ──A2A──> Marketing Agent ──HTTP──> LLM (configurable)
                      (this service)
```

The orchestrator sends campaign parameters via A2A `tasks/send`. This agent calls the LLM to generate bilingual email content, then returns the result as a task artifact.
