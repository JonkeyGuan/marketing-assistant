# MongoDB MCP

FastMCP server that exposes MongoDB customer/prospect data as MCP tools. Supports tier-based filtering, spend-based queries, and text search. Auto-seeds the database on first startup if no data exists.

Part of the [Marketing AI Assistant](../README.md) project.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)
- MongoDB instance (local or remote)

## Project Structure

```
mongodb-mcp/
├── app/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (uv run app)
│   ├── settings.py           # Pydantic settings
│   ├── server.py             # FastMCP tool definitions & MongoDB queries
│   └── seed_data.py          # Seed data for initial database population
├── k8s.yaml                  # OpenShift manifests (Deployment + Service + ConfigMap)
├── Containerfile
├── pyproject.toml
└── build.sh
```

## Local Development

```bash
# Start MongoDB (if not already running)
# e.g., podman run -d -p 27017:27017 mongo:7

# Install dependencies
uv sync

# (Optional) create a .env with overrides
cp .env.example .env   # if available

# Run the server
uv run app
```

Verify the server is running:

```bash
curl http://localhost:8082/healthz
```

## Build & Deploy to OpenShift

### Build the container image

```bash
./build.sh            # pushes quay.io/jonkey/marketing-assistant/mongodb-mcp:latest
./build.sh v1.2.0     # pushes quay.io/jonkey/marketing-assistant/mongodb-mcp:v1.2.0
```

### Apply manifests

```bash
oc apply -f k8s.yaml -n $NAMESPACE
oc rollout status deployment/mongodb-mcp -n $NAMESPACE
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8082` | HTTP listen port |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `MONGODB_DATABASE` | `casino_crm` | Database name for customer data |
| `LOG_LEVEL` | `INFO` | Python log level |

## Interface

**Protocol:** MCP (Model Context Protocol) via FastMCP

**MCP Tools:**

| Tool | Description |
|---|---|
| `get_customers_by_tier` | Retrieve customers filtered by membership tier (platinum, gold, diamond) |
| `get_prospects` | Retrieve prospect records |
| `get_all_vip_customers` | Retrieve all VIP-tier customers |
| `get_high_spend_customers` | Retrieve customers exceeding a spend threshold |
| `search_customers` | Full-text search across customer records |
| `get_customer_count_by_tier` | Return customer counts grouped by tier |

## Testing

MCP uses streamable-http transport. Requests require `Accept: application/json, text/event-stream` header.

```bash
# 1. Health check
curl http://localhost:8082/healthz

# 2. Initialize MCP session and save session ID
SESSION=$(curl -s -D - -X POST localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  2>&1 | grep -i mcp-session-id | tr -d '\r' | awk '{print $2}')

echo "Session: $SESSION"

# 3. Query all VIP customers
curl -X POST localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_all_vip_customers",
      "arguments": {"limit": 5}
    }
  }'

# 4. Search customers by name
curl -X POST localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "search_customers",
      "arguments": {"query": "zhang"}
    }
  }'
```

On first startup, the server auto-seeds MongoDB with customer and prospect data from the vertical config. If data already exists, seeding is skipped.

## Architecture

```
Customer Analyst (MCP client)
       │
       ▼ (MCP tool calls)
  MongoDB MCP
       │
       ▼
    MongoDB
```
