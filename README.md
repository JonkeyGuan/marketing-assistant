# Marketing AI Assistant

> Forked from [gymnatics/Marketing-Assistant-Demo](https://github.com/gymnatics/Marketing-Assistant-Demo) with modifications for persistent storage (PVC), campaign lifecycle management (delete + K8s cleanup), SSE event streaming, production deployment workflow, RBAC hardening and more.

An AI-powered Marketing Campaign Assistant that accelerates campaign creation through a web UI. The system uses a multi-agent architecture where each agent is an independent microservice communicating via the [Google A2A v1.0 protocol](https://github.com/a2aproject/a2a-python) and [MCP](https://modelcontextprotocol.io/), deployable on Red Hat OpenShift AI (RHOAI).

## Features

- Create marketing campaigns through a guided wizard UI
- Generate landing pages with AI (HTML/CSS/JS)
- AI-powered policy review and brand compliance guardrails
- 4-layer content safety: regex competitor filter, HAP detection, prompt injection detection, LLM policy review
- Generate and send bilingual marketing emails (English / 中文)
- Retrieve customer profiles for personalized targeting
- Real-time progress tracking via Server-Sent Events
- Human-in-the-loop approval workflows (preview → go live)
- Containerize and deploy campaigns to OpenShift
- Vertical configuration — switch industries without code changes

## Architecture

```mermaid
graph TB
    subgraph Presentation & BFF
        Frontend["Frontend<br/>(React SPA) :3000"]
        CampaignAPI["Campaign API<br/>(Flask BFF) :8089"]
        Frontend -->|REST| CampaignAPI
    end

    subgraph Event Streaming
        EventHub["Event Hub<br/>(SSE) :8080"]
        Frontend <-.->|SSE| EventHub
    end

    subgraph Orchestration
        Director["Campaign Director<br/>(LangGraph) :8088"]
    end

    CampaignAPI -->|A2A| PolicyGuardian
    CampaignAPI -->|A2A| Director
    Director -->|publish events| EventHub

    subgraph Agents
        CreativeProducer["Creative Producer :8086"]
        CustomerAnalyst["Customer Analyst :8084"]
        PolicyGuardian["Policy Guardian :8085"]
        DeliveryManager["Delivery Manager :8087"]
    end

    Director -->|A2A| CreativeProducer
    Director -->|A2A| CustomerAnalyst
    Director -->|A2A| PolicyGuardian
    Director -->|A2A| DeliveryManager

    subgraph MCP Servers
        ImagegenMCP["ImageGen MCP :8083"]
        MongoDBMCP["MongoDB MCP :8082"]
    end

    CreativeProducer -->|MCP| ImagegenMCP
    CustomerAnalyst -->|MCP| MongoDBMCP

    subgraph "TrustyAI Guardrails (optional)"
        HAPDetector["HAP Detector<br/>(granite-guardian-hap-125m)"]
        PIDetector["Prompt Injection Detector<br/>(deberta-v3-prompt-injection)"]
    end

    CampaignAPI -->|REST| HAPDetector
    CampaignAPI -->|REST| PIDetector

    subgraph Infrastructure
        ConfigService["Config Service :8081<br/><i>All services fetch vertical config at startup</i>"]
        LLM["LLM Endpoints<br/>(vLLM / OpenAI)"]
        MongoDB[(MongoDB :27017)]
        CampaignLanding["Campaign Landing<br/>(Express.js)"]
    end

    ImagegenMCP --> LLM
    CreativeProducer --> LLM
    PolicyGuardian --> LLM
    DeliveryManager --> LLM
    DeliveryManager -->|K8s API| CampaignLanding
    MongoDBMCP --> MongoDB

    Agents -.->|publish events| EventHub
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
├── infra/
│   ├── kagenti/            # Kagenti platform install/uninstall
│   └── guardrails/         # TrustyAI guardrails (HAP, prompt injection, orchestrator)
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

## Observability

Agent LLM calls are automatically traced via [OpenTelemetry](https://opentelemetry.io/) and MLflow. Each agent uses MLflow's tracing SDK to instrument workflows and LLM calls, exporting spans via OTLP to the kagenti platform's otel-collector, which forwards them to MLflow.

**Architecture**: Agent (MLflow SDK) → OTLP → otel-collector (kagenti-system) → MLflow Server

Environment variables (set in `k8s.yaml` / `.k8s.yaml`):

| Variable | Description |
|---|---|
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | otel-collector HTTP endpoint for traces |
| `OTEL_SERVICE_NAME` | Identifies the agent in trace views (e.g. `campaign-director`) |

### Trace metadata

MLflow UI displays three key columns populated by span attributes:

| Column | Span attribute | Source |
|---|---|---|
| **Trace name** | `mlflow.traceName` | Set by `_TraceNameProcessor` in `otel_setup.py` (root span name). A PostgreSQL trigger on the MLflow DB also sets this for OTLP-ingested traces (workaround until MLflow v3.13+). |
| **Session** | `session.id` | Campaign ID, set by each agent on its root span. |
| **User** | `user.id` | Keycloak `preferred_username` extracted from the JWT bearer token in campaign-director. Sub-agents inherit the parent trace context via `traceparent` header propagation. |

### Trace context propagation

Campaign-director sends `traceparent` HTTP headers when calling sub-agents via A2A. Each sub-agent captures these headers through `TraceContextMiddleware` (Starlette middleware) and restores the trace context so all spans join the same distributed trace.

Traces are visible in the kagenti MLflow UI under the `marketing-assistant` experiment.

## Deploy to OpenShift (Kagenti)

### Prerequisites

1. Logged in to OpenShift (`oc login`)
2. [LLM models](infra/models/) deployed manually to the `models` namespace (Qwen3-32B, Qwen3-Coder-30B, Flux2-Klein-4B)
3. [Kagenti platform](infra/kagenti/) installed (`infra/kagenti/install.sh`)
4. [TrustyAI Guardrails](infra/guardrails/) installed (optional, `infra/guardrails/install.sh`)
5. Container images built and pushed (each service has `build.sh`)
6. Secrets configured: copy `k8s.yaml` to `.k8s.yaml` per service and fill in `MODEL_ENDPOINT`, `MODEL_API_KEY`, `MONGODB_URI`, `CLUSTER_DOMAIN` etc.

### Deploy

```bash
./deploy.sh
```

This script handles:
- Namespace creation with kagenti labels
- `vertical-config` ConfigMap (config-service verticals)
- AuthBridge config sync + SCC grants (kagenti sidecar injection)
- All service manifests (`.k8s.yaml` priority, fallback to `k8s.yaml`)
- Keycloak SSO: `marketing-ui` client (public, PKCE), demo users (alice/bob), roles

### Uninstall

```bash
./undeploy.sh
```

Removes all application resources, Keycloak client/users/roles, and the namespace.

### TrustyAI Guardrails (Optional)

TrustyAI Guardrails is optional because it requires **Red Hat OpenShift AI 3.3+** with the TrustyAI component enabled (`trustyai.managementState: Managed` in DataScienceCluster CR). Without RHOAI, the GuardrailsOrchestrator CRD is unavailable and the detector InferenceServices cannot be deployed. campaign-api is designed for graceful degradation — when detector URLs are empty, the corresponding guardrail layers are skipped and the system operates with regex + Policy Guardian only.

```bash
# Install (default namespace: models)
infra/guardrails/install.sh

# Uninstall
infra/guardrails/uninstall.sh
```

campaign-api connects to the detectors via environment variables in `k8s.yaml`:

| Env Var | Purpose | Default |
|---|---|---|
| `HAP_DETECTOR_URL` | Hate/abuse/profanity detection | `""` (skip) |
| `PROMPT_INJECTION_URL` | Prompt injection detection | `""` (skip) |
| `ORCHESTRATOR_URL` | Orchestrator regex (gRPC-only, currently unused) | `""` (skip) |

When guardrails are deployed, set the URLs to point to the detector services (e.g. `http://guardrails-detector-ibm-hap-predictor.models.svc.cluster.local:8000`). See [`infra/guardrails/README.md`](infra/guardrails/README.md) for full architecture and testing details.

### Manual image build

```bash
cd <service> && ./build.sh <tag>
```

Services requiring rebuild for kagenti: `frontend` (SSO integration) and `campaign-api` (token forwarding).

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
