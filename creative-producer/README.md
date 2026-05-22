# Creative Producer

A2A agent that generates campaign landing pages using the "Bones & Beauty" architecture -- LLM generates CSS and content, then merges into an HTML skeleton template. Includes hero image generation via ImageGen MCP.

Part of the [Marketing Assistant](../README.md) multi-agent system.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenAI-compatible LLM endpoint (code model)
- ImageGen MCP service (for hero image generation, optional)

## Project Structure

```
creative-producer/
├── app/
│   ├── __init__.py
│   ├── __main__.py              # Entry point (uv run app)
│   ├── settings.py              # Pydantic settings
│   ├── agent.py                 # Landing page generation logic
│   ├── agent_executor.py        # A2A agent executor
│   └── base_template.html       # HTML skeleton for "Bones & Beauty" merge
├── k8s.yaml                     # OpenShift manifests (Deployment + Service + ConfigMap)
├── Containerfile
├── pyproject.toml
└── build.sh
```

## Local Development

```bash
# Install dependencies
uv sync

# (Optional) create a .env with overrides
cp .env.example .env

# Run the agent
uv run app
```

Verify the agent is running:

```bash
curl http://localhost:8086/healthz
```

## Build & Deploy to OpenShift

### Build the container image

```bash
./build.sh            # pushes quay.io/jonkey/marketing-assistant/creative-producer:latest
./build.sh v1.2.0     # pushes quay.io/jonkey/marketing-assistant/creative-producer:v1.2.0
```

### Configure secrets

Edit `k8s.yaml`, replace `<TODO>` in the Secret with actual values for `MODEL_ENDPOINT` and `MODEL_API_KEY`.

### Apply manifests

```bash
oc apply -f k8s.yaml -n $NAMESPACE
oc rollout status deployment/creative-producer -n $NAMESPACE
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8086` | HTTP listen port |
| `MODEL_ENDPOINT` | _(empty)_ | OpenAI-compatible LLM endpoint |
| `MODEL_NAME` | `qwen25-coder-32b-fp8` | Model name for code generation |
| `MODEL_API_KEY` | _(empty, optional)_ | API key for LLM auth (set via Secret) |
| `EVENT_HUB_URL` | `http://localhost:8080` | Event hub URL for status events |
| `IMAGEGEN_MCP_URL` | `http://localhost:8083` | ImageGen MCP URL for hero images |
| `LOG_LEVEL` | `INFO` | Python log level |

## Interface

**Protocol:** Google A2A v1.0 (JSON-RPC 2.0)

**Skills:**

| Skill | Description |
|---|---|
| `generate_landing_page` | Create a themed landing page with hero image for a campaign |

## Testing

Optionally start imagegen-mcp (port 8083) for hero image generation.

```bash
# 1. Health check
curl http://localhost:8086/healthz

# 2. Agent card
curl http://localhost:8086/.well-known/agent-card.json

# 3. Generate landing page (luxury_gold theme)
curl -s -X POST http://localhost:8086/ \
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
        "parts": [{"text": "{\"campaign_name\":\"Summer Retreat\",\"campaign_description\":\"VIP getaway\",\"hotel_name\":\"Simon Resort\",\"theme\":\"luxury_gold\",\"start_date\":\"2026-07-01\",\"end_date\":\"2026-08-31\"}"}]
      }
    }
  }'

# 4. Try a different theme (festive_red)
curl -s -X POST http://localhost:8086/ \
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
        "parts": [{"text": "{\"campaign_name\":\"Spring Festival Gala\",\"campaign_description\":\"New Year celebration\",\"hotel_name\":\"Simon Resort\",\"theme\":\"festive_red\",\"start_date\":\"2027-01-28\",\"end_date\":\"2027-02-10\"}"}]
      }
    }
  }' 

# 5. Preview generated HTML in browser
curl -s -X POST http://localhost:8086/ \
  -H "Content-Type: application/json" \
  -H "A2A-Version: 1.0" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "SendMessage",
    "params": {
      "message": {
        "messageId": "test-003",
        "role": "ROLE_USER",
        "parts": [{"text": "{\"campaign_name\":\"Night Poker Elite\",\"campaign_description\":\"VIP poker night\",\"hotel_name\":\"Simon Resort\",\"theme\":\"modern_black\",\"start_date\":\"2026-09-01\",\"end_date\":\"2026-09-30\"}"}]
      }
    }
  }' | jq -r '.result.task.artifacts[0].parts[0].text' \
     | jq -r '.html' > /tmp/page.html && open /tmp/page.html
```

Available themes: `luxury_gold`, `festive_red`, `modern_black`, `classic_emerald`.

Tests 3-4 should return `TASK_STATE_COMPLETED`. Test 5 opens the generated page in a browser.

## Architecture

```
Campaign Director
       │
       ▼ (A2A)
Creative Producer ──► Code LLM (CSS + content)
       │
       ▼ (MCP)
  ImageGen MCP (hero image)
```

The Creative Producer uses a "Bones & Beauty" approach: the HTML skeleton (`base_template.html`) provides structure, while the LLM generates CSS styling and content copy. The ImageGen MCP generates campaign-specific hero images. All pieces are merged into the final landing page.
