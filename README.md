# Marketing AI Assistant

An AI-powered Marketing Campaign Assistant designed to accelerate marketing campaign creation through natural language conversation. The system uses a multi-agent architecture where each agent is an independent microservice communicating via the [Google A2A protocol](https://github.com/a2aproject/a2a-python), deployable on Red Hat OpenShift AI (RHOAI).

## Features

- Generate marketing webpages through natural language conversation
- Automatically containerize and deploy campaigns to OpenShift
- Human-in-the-loop approval workflows (preview → go live)
- Generate and send bilingual marketing emails (English / 中文)
- Retrieve customer profiles for personalized targeting

## Architecture

```
                          ┌──────────────────┐
                          │   Streamlit UI   │
                          │  (orchestrator)  │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │    LangGraph     │
                          │   Orchestrator   │
                          └────────┬─────────┘
                                   │ A2A (JSON-RPC)
              ┌────────────┬───────┴───────┬────────────┐
              ▼            ▼               ▼            ▼
        ┌──────────┐ ┌──────────┐   ┌──────────┐ ┌──────────┐
        │  Coder   │ │ Customer │   │Marketing │ │   K8s    │
        │  Agent   │ │  Agent   │   │  Agent   │ │  Agent   │
        │  :8001   │ │  :8002   │   │  :8003   │ │  :8004   │
        └────┬─────┘ └──────────┘   └────┬─────┘ └────┬─────┘
             │                           │            │
             ▼                           ▼            ▼
         Code LLM                   Marketing LLM  OpenShift API
```

## Services

| Service | Port | Description |
|---|---|---|
| [orchestrator](orchestrator/) | 8501 | LangGraph workflow + Streamlit UI |
| [coder-agent](coder-agent/) | 8001 | Generates HTML/CSS/JS marketing landing pages |
| [customer-agent](customer-agent/) | 8002 | Retrieves customer profiles for targeting |
| [marketing-agent](marketing-agent/) | 8003 | Generates bilingual email content |
| [k8s-agent](k8s-agent/) | 8004 | Builds and deploys containers to OpenShift |

## Project Structure

```
marketing-assistant/
├── orchestrator/          # LangGraph orchestrator + Streamlit UI
├── coder-agent/           # A2A agent: HTML generation
├── customer-agent/        # A2A agent: customer data
├── marketing-agent/       # A2A agent: email generation
└── k8s-agent/             # A2A agent: OpenShift deployment
```

Each service follows the same project layout:

```
<service>/
  app/
    __init__.py
    __main__.py            # Entry point (uv run app)
    executor.py            # Agent logic (A2A agents only)
    settings.py            # Pydantic settings
  k8s/                     # OpenShift manifests
  Containerfile
  build.sh
  pyproject.toml
  .env.example
```

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)
- Access to OpenAI-compatible LLM endpoints (for coder-agent and marketing-agent)
- OpenShift cluster (for k8s-agent and production deployment)

## Quick Start

### 1. Start all agents

```bash
# Terminal 1
cd coder-agent && cp .env.example .env && uv sync && uv run app

# Terminal 2
cd customer-agent && cp .env.example .env && uv sync && uv run app

# Terminal 3
cd marketing-agent && cp .env.example .env && uv sync && uv run app

# Terminal 4
cd k8s-agent && cp .env.example .env && uv sync && uv run app
```

### 2. Start the orchestrator

```bash
cd orchestrator && cp .env.example .env && uv sync && uv run app
```

Open `http://localhost:8501` in your browser.

## User Flow

1. **Welcome** — Select "Create Campaign"
2. **Campaign Details** — Provide name, description, dates, and target audience
3. **Theme Selection** — Choose from 4 visual themes (Luxury Gold, Festive Red, Modern Black, Classic Casino)
4. **Generation** — Coder Agent generates webpage → K8s Agent deploys preview
5. **Preview** — Review campaign with QR code, edit or approve
6. **Go Live** — K8s Agent promotes to production → Customer Agent retrieves recipients → Marketing Agent generates emails

## Deploy to OpenShift

Each service can be independently built and deployed:

```bash
# Build and push container images
cd coder-agent && ./build.sh
cd customer-agent && ./build.sh
cd marketing-agent && ./build.sh
cd k8s-agent && ./build.sh
cd orchestrator && ./build.sh

# Apply Kubernetes manifests
NAMESPACE=0-marketing-assistant-demo
oc apply -f coder-agent/k8s/ -n $NAMESPACE
oc apply -f customer-agent/k8s/ -n $NAMESPACE
oc apply -f marketing-agent/k8s/ -n $NAMESPACE
oc apply -f k8s-agent/k8s/ -n $NAMESPACE
oc apply -f orchestrator/k8s/ -n $NAMESPACE
```

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Orchestration | Python 3.11+, LangGraph |
| Agent Protocol | Google A2A (JSON-RPC 2.0) |
| Agent SDK | a2a-sdk |
| Models | Configurable LLMs (via vLLM / OpenAI-compatible) |
| Platform | Red Hat OpenShift AI (RHOAI) |
| Container Build | Podman / Buildah |
| Package Manager | UV |

## License

MIT License
