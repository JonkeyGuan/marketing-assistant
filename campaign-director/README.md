# Campaign Director

LangGraph orchestrator that manages the campaign creation workflow -- landing page generation, email preview, and go-live deployment -- by coordinating downstream A2A agents.

Part of the [Marketing Assistant](../README.md) multi-agent system. Runs as a standalone service, communicates with upstream and downstream services via the [Google A2A protocol](https://github.com/a2aproject/a2a-python).

## Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/)

## Project Structure

```
campaign-director/
├── app/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (uvicorn + A2A server)
│   ├── settings.py          # Environment-based configuration
│   ├── agent.py             # LangGraph workflow definition
│   └── agent_executor.py    # AgentExecutor: handles A2A task lifecycle
├── k8s.yaml                 # OpenShift manifests (Deployment + Service + ConfigMap)
├── Containerfile
├── pyproject.toml
└── build.sh
```

## Local Development

```bash
uv sync
uv run app
```

Verify:

```bash
curl http://localhost:8088/healthz
curl http://localhost:8088/.well-known/agent-card.json
```

## Build & Deploy to OpenShift

### 1. Build & push image

```bash
./build.sh          # default: latest
./build.sh v1.0.0   # or with a specific tag
```

### 2. Apply manifests

```bash
NAMESPACE=<your-namespace>

oc apply -f k8s.yaml -n $NAMESPACE
oc rollout status deployment/campaign-director -n $NAMESPACE
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `PORT` | Server listen port | `8088` |
| `CREATIVE_PRODUCER_URL` | URL of the Creative Producer A2A agent | -- |
| `CUSTOMER_ANALYST_URL` | URL of the Customer Analyst A2A agent | -- |
| `DELIVERY_MANAGER_URL` | URL of the Delivery Manager A2A agent | -- |
| `POLICY_GUARDIAN_URL` | URL of the Policy Guardian service | -- |
| `EVENT_HUB_URL` | URL of the Event Hub SSE service | -- |
| `CLUSTER_DOMAIN` | OpenShift cluster domain for route generation | -- |
| `DEV_NAMESPACE` | Development namespace for deployments | -- |
| `PROD_NAMESPACE` | Production namespace for deployments | -- |
| `LOG_LEVEL` | Logging level | `INFO` |

## A2A Interface

**Protocol:** Google A2A v1.0 (JSON-RPC 2.0)

**Skills:**

| Skill | Description |
|---|---|
| `create_campaign` | Create a new campaign record |
| `generate_landing_page` | Generate landing page via Creative Producer |
| `prepare_email_preview` | Retrieve customers and generate email content |
| `go_live` | Deploy to production and send emails |

## Testing

The Campaign Director orchestrates downstream agents. For a full test, start the dependent services first:
- Policy Guardian (8085)
- Creative Producer (8086)
- Delivery Manager (8087)
- Customer Analyst (8084)

```bash
# 1. Health check
curl http://localhost:8088/healthz

# 2. Agent card
curl http://localhost:8088/.well-known/agent-card.json

# 3. Create a campaign via A2A
curl -s -X POST http://localhost:8088/ \
  -H "Content-Type: application/json" \
  -H "A2A-Version: 1.0" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "SendMessage",
    "params": {
      "message": {
        "messageId": "test-001",
        "role": "ROLE_USER",
        "parts": [{"text": "{\"skill\":\"create_campaign\",\"campaign_name\":\"Summer Retreat\",\"campaign_description\":\"VIP luxury getaway\",\"hotel_name\":\"Simon Resort\",\"target_audience\":\"Platinum members\",\"theme\":\"luxury_gold\",\"start_date\":\"2026-07-01\",\"end_date\":\"2026-08-31\"}"}]
      }
    }
  }'

# 4. Check campaign status via REST
curl http://localhost:8088/campaigns

# 5. Generate landing page (replace CAMPAIGN_ID from step 3)
curl -s -X POST http://localhost:8088/ \
  -H "Content-Type: application/json" \
  -H "A2A-Version: 1.0" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "SendMessage",
    "params": {
      "message": {
        "messageId": "test-002",
        "role": "ROLE_USER",
        "parts": [{"text": "{\"skill\":\"generate_landing_page\",\"campaign_id\":\"CAMPAIGN_ID\"}"}]
      }
    }
  }'
```

Test 3 returns `TASK_STATE_COMPLETED` with a `campaign_id`. Test 5 triggers the landing page workflow asynchronously — poll `/campaigns/{id}` to check progress.

```bash
# 6. Preview generated landing page in browser (replace CAMPAIGN_ID)
curl -s http://localhost:8088/campaigns/CAMPAIGN_ID | python3 -c "import sys,json; html=json.load(sys.stdin).get('landing_page_html',''); open('/tmp/page.html','w').write(html)" && open /tmp/page.html
```

## Architecture

```
campaign-api --> Campaign Director (LangGraph) --+--> Creative Producer
               (this service)                    +--> Customer Analyst
                                                 +--> Delivery Manager
                                                 +--> Policy Guardian
```

The Campaign Director receives campaign requests via A2A, executes a LangGraph workflow that coordinates downstream agents, and returns aggregated results.
