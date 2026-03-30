# Customer Agent

A2A (Agent-to-Agent) microservice that retrieves VIP customer profiles from CRM for marketing campaigns.

Part of the [Marketing Assistant](../README.md) multi-agent system. Runs as a standalone service, communicates with the orchestrator via the [Google A2A protocol](https://github.com/a2aproject/a2a-python).

## Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/)
- MongoDB (optional, falls back to mock data)

## Project Structure

```
customer-agent/
  app/
    __init__.py
    __main__.py                  # Entry point: assembles & starts A2A server
    executor.py                  # AgentExecutor: handles A2A task lifecycle
    customer_query.py            # Core skill: query customer profiles
    settings.py                  # Environment-based configuration
  k8s/                           # OpenShift deployment manifests
  Containerfile
  pyproject.toml
```

## Local Development

```bash
cp .env.example .env            # edit with your MongoDB URI
uv sync
uv run app
```

Verify:

```bash
curl http://localhost:8002/.well-known/agent.json
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
oc rollout status deployment/customer-agent -n $NAMESPACE
```

### 3. Verify

```bash
# External
ROUTE=$(oc get route customer-agent -n $NAMESPACE -o jsonpath='{.spec.host}')
curl https://$ROUTE/.well-known/agent.json

# In-cluster URL (for orchestrator configmap)
# http://customer-agent.${NAMESPACE}.svc.cluster.local:8002
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `casino_crm` |
| `CUSTOMER_A2A_PORT` | Server listen port | `8002` |

## A2A Interface

**Skill:** `query_customers`

**Input** (via `DataPart`):
```json
{
  "target_audience": "VIP platinum members"
}
```

**Output** (artifact):
```json
{
  "customers": [
    {
      "customer_id": "VIP-001",
      "name_en": "Wei Zhang",
      "email": "wei.zhang@example.com",
      "tier": "platinum",
      "preferred_language": "zh-CN",
      "interests": ["baccarat", "fine dining", "spa"],
      "total_spend": 500000
    }
  ]
}
```

## Architecture

```
Orchestrator ──A2A──> Customer Agent ──MongoDB──> CRM Database
                      (this service)      (optional, mock fallback)
```

The orchestrator sends target audience parameters via A2A `tasks/send`. This agent queries the CRM database and returns matching customer profiles as a task artifact.
