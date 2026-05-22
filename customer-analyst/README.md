# Customer Analyst

A2A agent that retrieves and analyzes customer data by calling MongoDB MCP tools. Uses LLM for intelligent tool selection in real mode; falls back to keyword matching + seed data in mock mode.

Part of the [Marketing AI Assistant](../README.md) project.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenAI-compatible LLM endpoint (real mode)
- Running [mongodb-mcp](../mongodb-mcp/) instance (real mode)

## Project Structure

```
customer-analyst/
├── app/
│   ├── __init__.py
│   ├── __main__.py           # Entry point (uv run app)
│   ├── settings.py           # Pydantic settings
│   ├── agent.py              # Skill definitions & LLM tool-calling logic
│   └── agent_executor.py     # A2A agent executor
├── k8s.yaml                  # OpenShift manifests (Deployment + Service + ConfigMap)
├── Containerfile
├── pyproject.toml
└── build.sh
```

## Local Development

```bash
# Install dependencies
uv sync

# (Optional) create a .env with overrides
cp .env.example .env   # if available

# Run the agent
uv run app
```

Verify the agent is running:

```bash
curl http://localhost:8084/healthz
```

## Build & Deploy to OpenShift

### Build the container image

```bash
./build.sh            # pushes quay.io/jonkey/marketing-assistant/customer-analyst:latest
./build.sh v1.2.0     # pushes quay.io/jonkey/marketing-assistant/customer-analyst:v1.2.0
```

### Configure secrets

Edit `k8s.yaml`, replace `<TODO>` in the Secret with actual values for `MODEL_ENDPOINT` and `MODEL_API_KEY`.

### Apply manifests

```bash
oc apply -f k8s.yaml -n $NAMESPACE
oc rollout status deployment/customer-analyst -n $NAMESPACE
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8084` | HTTP listen port |
| `MONGODB_MCP_URL` | `http://localhost:8082` | MongoDB MCP server URL |
| `EVENT_HUB_URL` | `http://localhost:8080` | Event hub URL for status events |
| `MODEL_ENDPOINT` | _(empty)_ | OpenAI-compatible model endpoint |
| `MODEL_NAME` | `qwen3-32b-fp8-dynamic` | Model name for tool selection |
| `MODEL_API_KEY` | _(empty, optional)_ | API key for the model endpoint (set via Secret) |
| `LOG_LEVEL` | `INFO` | Python log level |

## Interface

**Protocol:** Google A2A v1.0 (JSON-RPC 2.0)

**Skills:**

| Skill | Description |
|---|---|
| `get_target_customers` | Retrieve customers matching target audience criteria |

## Testing

Requires mongodb-mcp (port 8082) and MongoDB to be running.

```bash
# 1. Health check
curl http://localhost:8084/healthz

# 2. Agent card
curl http://localhost:8084/.well-known/agent-card.json

# 3. Send A2A request (get Platinum customers)
curl -X POST http://localhost:8084/ \
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
        "parts": [{"text": "{\"user_prompt\": \"Get all Platinum tier customers\", \"campaign_id\": \"test\"}"}]
      }
    }
  }'
```

Expected response: a JSON-RPC result containing a task with `TASK_STATE_COMPLETED` status and an artifact with customer data.

## Architecture

```
Campaign Director
       │
       ▼ (A2A)
Customer Analyst
       │
       ▼ (MCP tool calls)
MongoDB MCP ──► MongoDB
```
