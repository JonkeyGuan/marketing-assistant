# Orchestrator

LangGraph workflow orchestrator with Streamlit UI for the Marketing AI Assistant.

Part of the [Marketing Assistant](../README.md) multi-agent system. Coordinates campaign creation by calling four A2A agent microservices via the [Google A2A protocol](https://github.com/a2aproject/a2a-python).

## Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/)
- All A2A agent services running (coder-agent, customer-agent, marketing-agent, k8s-agent)

## Project Structure

```
orchestrator/
  app/
    __init__.py
    __main__.py                 # Entry point: launches Streamlit
    ui.py                       # Streamlit UI application
    orchestrator.py             # LangGraph StateGraph workflow
    state.py                    # CampaignState & theme definitions
    settings.py                 # Environment-based configuration
    a2a/
      __init__.py
      client.py                 # A2A JSON-RPC client
      models.py                 # A2A protocol data models
  k8s/                          # OpenShift deployment manifests
  Containerfile
  pyproject.toml
```

## Local Development

```bash
cp .env.example .env            # edit with your agent URLs
uv sync
uv run app
```

The UI will be available at `http://localhost:8501`.

Make sure all four A2A agent services are running before starting the orchestrator:

```bash
# In separate terminals
cd ../coder-agent    && uv run app    # http://localhost:8001
cd ../customer-agent && uv run app    # http://localhost:8002
cd ../marketing-agent && uv run app   # http://localhost:8003
cd ../k8s-agent      && uv run app    # http://localhost:8004
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
oc rollout status deployment/marketing-assistant -n $NAMESPACE
```

### 3. Verify

```bash
ROUTE=$(oc get route marketing-assistant -n $NAMESPACE -o jsonpath='{.spec.host}')
echo "https://$ROUTE"
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `CODER_A2A_URL` | Coder Agent endpoint | `http://coder-agent.…:8001` |
| `CUSTOMER_A2A_URL` | Customer Agent endpoint | `http://customer-agent.…:8002` |
| `MARKETING_A2A_URL` | Marketing Agent endpoint | `http://marketing-agent.…:8003` |
| `K8S_A2A_URL` | K8s Agent endpoint | `http://k8s-agent.…:8004` |
| `EMAIL_MODE` | Email mode: `simulate` or `send` | `simulate` |
| `RESEND_API_KEY` | Resend API key (when EMAIL_MODE=send) | — |
| `SERVICE_PORT` | Streamlit server port | `8501` |
| `DEBUG` | Enable debug mode | `true` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `SUPPORTED_LANGUAGES` | Supported languages | `en,zh-CN` |
| `DEFAULT_LANGUAGE` | Default language | `en` |

On OpenShift, these are configured via `k8s/configmap.yaml` (non-sensitive) and `marketing-assistant-secrets` Secret (sensitive values).

## User Flow

1. **Welcome** — User selects "Create Campaign"
2. **Campaign Details** — User provides campaign name, description, dates, and target audience
3. **Theme Selection** — User selects from 4 visual themes (Luxury Gold, Festive Red, Modern Black, Classic Casino)
4. **Generation** — Orchestrator calls Coder Agent (generate HTML) → K8s Agent (deploy preview)
5. **Preview** — User reviews campaign with QR code, can edit or go live
6. **Go Live** — K8s Agent promotes to production → Customer Agent retrieves recipients → Marketing Agent generates emails → Emails sent

## Architecture

```
                          ┌──────────────────┐
                          │   Streamlit UI   │
                          │    (main.py)      │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │    LangGraph     │
                          │  Orchestrator    │
                          │ (app/orchestrator)│
                          └────────┬─────────┘
                                   │ A2A (JSON-RPC)
              ┌────────────┬───────┴───────┬────────────┐
              ▼            ▼               ▼            ▼
        ┌──────────┐ ┌──────────┐   ┌──────────┐ ┌──────────┐
        │  Coder   │ │ Customer │   │Marketing │ │   K8s    │
        │  Agent   │ │  Agent   │   │  Agent   │ │  Agent   │
        │  :8001   │ │  :8002   │   │  :8003   │ │  :8004   │
        └──────────┘ └──────────┘   └──────────┘ └──────────┘
```

The orchestrator sends task parameters to each agent via A2A `tasks/send` and receives results as task artifacts. It does **not** call LLMs directly — all AI capabilities are delegated to the agent microservices.
