# ImageGen MCP

FastMCP server that generates campaign hero images via an image generation model API. Returns base64 data URIs for direct embedding in HTML, with a placeholder fallback in mock mode.

> Part of [Marketing AI Assistant](../README.md)

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Podman (for container builds)

## Project Structure

```
imagegen-mcp/
├── app/
│   ├── __init__.py
│   ├── __main__.py        # Entrypoint (uvicorn)
│   ├── settings.py        # Pydantic settings / env vars
│   └── server.py          # FastMCP tools & Starlette routes
├── k8s.yaml               # OpenShift manifests (Deployment + Service + ConfigMap)
├── Containerfile
├── pyproject.toml
└── build.sh
```

## Local Development

```bash
# Install dependencies
uv sync

# Run the server
uv run app

# Verify
curl http://localhost:8083/healthz
```

## Build & Deploy to OpenShift

```bash
# Build and push the container image
./build.sh          # defaults to :latest
./build.sh v1.0.0   # or specify a tag

# Configure secrets: edit k8s.yaml, replace <TODO> with actual values
# for MODEL_ENDPOINT, MODEL_NAME, and MODEL_API_KEY

# Apply manifests
oc apply -f k8s.yaml

# Verify the deployment
oc rollout status deployment/imagegen-mcp
curl http://localhost:8083/healthz
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8083` | HTTP listen port |
| `MODEL_ENDPOINT` | `""` | Base URL of the image generation API (e.g. `https://ai.api.nvidia.com/v1/genai/black-forest-labs`) |
| `MODEL_API_KEY` | `""` | API key for authentication. If empty, runs in mock mode (placeholder images) |
| `MODEL_NAME` | `flux2-klein-4b` | Model name for image generation |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## MCP Tools

| Tool | Description |
|---|---|
| `generate_campaign_image_b64` | Generate a hero banner and return the image as a base64 data URI |

Accepts: `campaign_name`, `hotel_name`, `theme` (`luxury_gold`, `festive_red`, `modern_black`, `classic_emerald`), `description`, `width`, `height`.

### HTTP Endpoints

| Path | Method | Description |
|---|---|---|
| `/mcp` | POST | MCP JSON-RPC endpoint |
| `/healthz` | GET | Health check |
| `/readyz` | GET | Readiness check |

## Testing

MCP uses streamable-http transport. Requests require `Accept: application/json, text/event-stream` header.

```bash
# 1. Health check
curl http://localhost:8083/healthz

# 2. Initialize MCP session and save session ID
SESSION=$(curl -s -D - -X POST localhost:8083/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  2>&1 | grep -i mcp-session-id | tr -d '\r' | awk '{print $2}')

echo "Session: $SESSION"

# 3. Call generate_campaign_image_b64 tool
curl -X POST localhost:8083/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "generate_campaign_image_b64",
      "arguments": {
        "campaign_name": "Spring Gala",
        "hotel_name": "Simon Casino Resort",
        "theme": "luxury_gold"
      }
    }
  }'

# 4. The returned data_uri can be used directly in an <img> tag
```

In mock mode (no API key), the tool returns a placeholder base64 data URI. With a valid API key, it calls the image generation model and returns the result as a base64 data URI for direct HTML embedding.

## Architecture

```
Creative Producer        ImageGen MCP              Image Gen Model API
  (MCP client)           (this service)            (e.g. NVIDIA Flux)
       │                      │                           │
       │  tools/call          │                           │
       ├─────────────────────►│  POST {ENDPOINT}/{MODEL}  │
       │                      ├──────────────────────────►│
       │                      │     artifacts/base64      │
       │                      │◄──────────────────────────┤
       │   base64 data URI    │                           │
       │◄─────────────────────┤                           │
       │                      │                           │
```
