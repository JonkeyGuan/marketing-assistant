# Policy Guardian

A2A agent that validates campaign content against business policies. In mock mode, auto-approves all campaigns. In real mode, uses LLM to check for compliance violations.

Part of the [Marketing AI Assistant](../README.md) project.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenAI-compatible LLM endpoint (real mode)

## Project Structure

```
policy-guardian/
├── app/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (uv run app)
│   ├── settings.py           # Pydantic settings
│   ├── agent.py              # Policy validation logic & LLM prompt
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
curl http://localhost:8085/healthz
```

## Build & Deploy to OpenShift

### Build the container image

```bash
./build.sh            # pushes quay.io/jonkey/marketing-assistant/policy-guardian:latest
./build.sh v1.2.0     # pushes quay.io/jonkey/marketing-assistant/policy-guardian:v1.2.0
```

### Configure secrets

Edit `k8s.yaml`, replace `<TODO>` in the Secret with actual values for `MODEL_ENDPOINT` and `MODEL_API_KEY`.

### Apply manifests

```bash
oc apply -f k8s.yaml -n $NAMESPACE
oc rollout status deployment/policy-guardian -n $NAMESPACE
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8085` | HTTP listen port |
| `MODEL_ENDPOINT` | _(empty)_ | OpenAI-compatible model endpoint |
| `MODEL_NAME` | `qwen3-32b-fp8-dynamic` | Model name for policy validation |
| `MODEL_API_KEY` | _(empty, optional)_ | API key for the model endpoint (set via Secret) |
| `EVENT_HUB_URL` | `http://localhost:8080` | Event hub URL for status events |
| `LOG_LEVEL` | `INFO` | Python log level |

## Interface

**Protocol:** Google A2A v1.0 (JSON-RPC 2.0)

**Skills:**

| Skill | Description |
|---|---|
| `validate_campaign` | Validate campaign content against business policies (discount limits, brand tone, compliance) |

## Testing

```bash
# 1. Health check
curl http://localhost:8085/healthz

# 2. Agent card
curl http://localhost:8085/.well-known/agent-card.json

# 3. Test a campaign that should be APPROVED
curl -X POST http://localhost:8085/ \
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
        "parts": [{"text": "{\"campaign_name\": \"Exclusive Platinum Spa Retreat\", \"campaign_description\": \"Complimentary spa treatment with 2-night stay for platinum members\"}"}]
      }
    }
  }'

# 4. Test a campaign that should be REJECTED (unrealistic discount)
curl -X POST http://localhost:8085/ \
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
        "parts": [{"text": "{\"campaign_name\": \"99% Off All Rooms\", \"campaign_description\": \"Get 99% discount on all hotel rooms this weekend\"}"}]
      }
    }
  }'
```

Test 3 should return `approved: true`. Test 4 should return `approved: false` with a rejection reason.

## Architecture

```
campaign-api / Campaign Director
       │
       ▼ (A2A)
Policy Guardian
       │
       ▼ (API call)
      LLM  (policy compliance check)
```
