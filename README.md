# Marketing AI Assistant

> Forked from [gymnatics/Marketing-Assistant-Demo](https://github.com/gymnatics/Marketing-Assistant-Demo) with modifications for persistent storage (PVC), campaign lifecycle management (delete + K8s cleanup), SSE event streaming, production deployment workflow, RBAC hardening and more.

An AI-powered Marketing Campaign Assistant that accelerates campaign creation through a web UI. The system uses a multi-agent architecture where each agent is an independent microservice communicating via the [Google A2A v1.0 protocol](https://github.com/a2aproject/a2a-python) and [MCP](https://modelcontextprotocol.io/), deployable on Red Hat OpenShift AI (RHOAI).

## Features

- Create marketing campaigns through a guided wizard UI
- Generate landing pages with AI (HTML/CSS/JS)
- AI-powered policy review and brand compliance guardrails
- Generate and send bilingual marketing emails (English / 中文)
- Retrieve customer profiles for personalized targeting
- Real-time progress tracking via Server-Sent Events
- Human-in-the-loop approval workflows (preview → go live)
- Containerize and deploy campaigns to OpenShift
- Vertical configuration — switch industries without code changes

## Architecture

```
┌─ Presentation & BFF ────────────────────────────────────────────────────┐
│                                                                         │
│  Frontend (React SPA) :3000 <──SSE──> Event Hub (SSE) :8080             │
│       |                                   |                             │
│       | REST                              ^ publish                     │
│       |                                   |                             │
│  Campaign API (Flask BFF) :8089 ──A2A──> Policy Guardian :8085 -> LLM   │
│                                                                         │
└───────|─────────────────────────────────────────────────────────────────┘
        | A2A v1.0
┌─ Orchestration ─────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌──────────────────────┐                                               │
│  │  Campaign Director   │── publish events ──> Event Hub                │
│  │  (LangGraph) :8088   │                                               │
│  └──────────────────────┘                                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
        | A2A v1.0
┌─ Agents ────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐             │
│  │ Creative │  │ Customer │  │ Policy   │  │  Delivery    │             │
│  │ Producer │  │ Analyst  │  │ Guardian │  │  Manager     │             │
│  │  :8086   │  │  :8084   │  │  :8085   │  │   :8087      │             │
│  └──┬───┬───┘  └──┬───┬───┘  └────┬─────┘  └──┬───┬───┬───┘             │
│     |   |         |   |          |             |   |   |                │
│   Code ImageGen MDB  LLM       LLM          LLM  K8s Campaign           │
│   LLM  MCP     MCP                          API       Landing           │
│        :8083   :8082                                                    │
│                                                                         │
│  All agents ── publish events ──> Event Hub                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─ Data ───────────────────────────────┐  ┌─ Infrastructure ───────────────┐
│                                      │  │                                │
│  MongoDB MCP :8082 -> MongoDB :27017 │  │  Config Service :8081          │
│                                      │  │                                │
│  ImageGen MCP :8083 -> ImageGen GPU  │  │  LLM Endpoints (vLLM/OpenAI)   │
│                                      │  │                                │
└──────────────────────────────────────┘  └────────────────────────────────┘

Protocols:  REST    A2A v1.0 (JSON-RPC 2.0)    MCP    SSE
```

## Services

| Service | Port | Protocol | Description |
|---|---|---|---|
| [event-hub](event-hub/) | 8080 | SSE | Real-time event bus for progress tracking |
| [config-service](config-service/) | 8081 | REST | Vertical configuration API — serves industry config |
| [mongodb-mcp](mongodb-mcp/) | 8082 | MCP | MongoDB customer data access |
| [imagegen-mcp](imagegen-mcp/) | 8083 | MCP | AI hero image generation |
| [customer-analyst](customer-analyst/) | 8084 | A2A v1.0 | Retrieves customer profiles via MongoDB MCP |
| [policy-guardian](policy-guardian/) | 8085 | A2A v1.0 | Campaign policy validation via LLM |
| [creative-producer](creative-producer/) | 8086 | A2A v1.0 | Generates HTML landing pages via Code LLM |
| [delivery-manager](delivery-manager/) | 8087 | A2A v1.0 | Emails, preview/production deployment |
| [campaign-director](campaign-director/) | 8088 | A2A v1.0 | LangGraph orchestrator — coordinates all agents |
| [campaign-api](campaign-api/) | 8089 | REST | Flask BFF with guardrail checks |
| [frontend](frontend/) | 3000 | HTTP | React SPA — campaign wizard, SSE progress, inbox |
| [campaign-landing](campaign-landing/) | — | HTTP | Express.js — serves personalized landing pages |

## Project Structure

```
marketing-assistant/
├── frontend/               # React SPA
├── campaign-api/           # Flask API gateway
├── campaign-director/      # LangGraph orchestrator
├── creative-producer/      # A2A agent: HTML generation
├── customer-analyst/       # A2A agent: customer data
├── delivery-manager/       # A2A agent: deployment & email
├── policy-guardian/        # A2A agent: policy validation
├── event-hub/              # SSE event bus
├── mongodb-mcp/            # MCP server: MongoDB
├── imagegen-mcp/           # MCP server: image generation
├── config-service/         # Vertical configuration REST API
├── campaign-landing/       # Landing page server
├── mongodb/                # MongoDB: local run/stop scripts + k8s manifests
├── run.sh                  # Start all services locally
└── stop.sh                 # Stop all services
```

Python services follow a common layout:

```
<service>/
  app/
    __init__.py
    __main__.py            # Entry point (uv run app)
    settings.py            # Pydantic settings
  k8s.yaml                 # OpenShift manifests
  Containerfile
  build.sh
  pyproject.toml
  .env.example
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for frontend and campaign-landing)
- Podman (for MongoDB)
- LLM endpoints optional (mock/fallback mode works without them)

## Quick Start

```bash
# Start all services
./run.sh

# Stop all services
./stop.sh
```

Or start individually in order:

```bash
# 1. MongoDB
cd mongodb && ./run.sh

# 2. Event Hub + Config Service
cd event-hub && uv sync && uv run app
cd config-service && uv sync && uv run app

# 3. MCP servers
cd mongodb-mcp && uv sync && uv run app
cd imagegen-mcp && uv sync && uv run app

# 4. Agents
cd customer-analyst && uv sync && uv run app
cd policy-guardian && uv sync && uv run app
cd creative-producer && uv sync && uv run app
cd delivery-manager && uv sync && uv run app

# 5. Orchestrator + API
cd campaign-director && uv sync && uv run app
cd campaign-api && uv sync && uv run app

# 6. Frontend
cd frontend && npm install && npm start
```

Open `http://localhost:3000` in your browser.

## Vertical Configuration

The system supports different industries via JSON config files served by the **config-service** (port 8081). The default vertical is `hotel-casino`.

To switch verticals, set the environment variable on config-service:

```bash
export VERTICAL_CONFIG=hotel-casino   # default
```

All other services fetch their configuration from config-service at startup via REST API. Each vertical config defines: brand identity, properties, customer tiers, themes, competitor names (for guardrails), LLM prompts, quick-start presets, and seed data. See [`config-service/app/verticals/hotel-casino.json`](config-service/app/verticals/hotel-casino.json) for the full schema.

## Deploy to OpenShift

```bash
NAMESPACE=<your-namespace>

# 1. Deploy MongoDB
oc apply -f mongodb/k8s.yaml -n $NAMESPACE

# 2. Build and push all images
for svc in campaign-api campaign-director creative-producer customer-analyst \
           delivery-manager policy-guardian event-hub mongodb-mcp imagegen-mcp \
           config-service campaign-landing frontend; do
  cd $svc && ./build.sh && cd ..
done

# 3. Create vertical config ConfigMap (not baked into image)
oc create configmap vertical-config \
  --from-file=config-service/app/verticals/ \
  -n $NAMESPACE

# 4. Configure secrets: edit k8s.yaml for each service, replace <TODO> with actual values
#    - mongodb-mcp:       MONGODB_URI
#    - creative-producer: MODEL_ENDPOINT, MODEL_API_KEY
#    - customer-analyst:  MODEL_ENDPOINT, MODEL_API_KEY
#    - delivery-manager:  MODEL_ENDPOINT, MODEL_API_KEY
#    - policy-guardian:   MODEL_ENDPOINT, MODEL_API_KEY
#    - imagegen-mcp:      MODEL_ENDPOINT, MODEL_API_KEY

# 5. Apply manifests
for svc in config-service event-hub mongodb-mcp imagegen-mcp customer-analyst \
           policy-guardian creative-producer delivery-manager campaign-director \
           campaign-api frontend; do
  oc apply -f $svc/k8s.yaml -n $NAMESPACE
done
```

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| BFF (Backend For Frontend) | Flask |
| Orchestration | Python 3.11+, LangGraph |
| Agent Protocol | Google A2A v1.0 (JSON-RPC 2.0) |
| Tool Protocol | Model Context Protocol (MCP) |
| Agent SDK | a2a-sdk v1.0.3, FastMCP |
| Models | Configurable LLMs (via vLLM / OpenAI-compatible) |
| Database | MongoDB |
| Platform | Red Hat OpenShift AI (RHOAI) |
| Container Build | Podman |
| Package Manager | uv (Python), npm (Node.js) |

## License

MIT License
