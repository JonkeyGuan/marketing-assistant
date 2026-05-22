# Delivery Manager

A2A agent that handles email generation (bilingual EN/ZH), K8s deployment of campaign landing pages, and simulated email delivery. Falls back to pre-canned templates and local:// URLs in mock mode.

Part of the [Marketing AI Assistant](../README.md) project.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)
- Access to an OpenAI-compatible LLM endpoint (real mode)
- OpenShift cluster with target namespaces (for deployment skills)
- Running [campaign-api](../campaign-api/) instance (for email delivery)

## Project Structure

```
delivery-manager/
├── app/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (uv run app)
│   ├── settings.py           # Pydantic settings
│   ├── agent.py              # Email gen, deploy, and send logic
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
curl http://localhost:8087/.well-known/agent-card.json
```

## Build & Deploy to OpenShift

### Build the container image

```bash
./build.sh            # pushes quay.io/jonkey/marketing-assistant/delivery-manager:latest
./build.sh v1.2.0     # pushes quay.io/jonkey/marketing-assistant/delivery-manager:v1.2.0
```

### Configure manifests

Edit `k8s.yaml` and replace all `<TODO>` placeholders:

| Placeholder | Location | Description |
|---|---|---|
| `MODEL_ENDPOINT` | Secret | OpenAI-compatible model endpoint URL |
| `MODEL_NAME` | Secret | Model name |
| `MODEL_API_KEY` | Secret | API key for the model endpoint |
| `CLUSTER_DOMAIN` | ConfigMap | OpenShift apps domain (e.g. `apps.cluster-xxx.sandbox.opentlc.com`) |
| `namespace` | ClusterRoleBinding | Namespace where delivery-manager is deployed (e.g. `marketing`) |

### Apply manifests

```bash
oc apply -f k8s.yaml -n $NAMESPACE
oc rollout status deployment/delivery-manager -n $NAMESPACE
```

### RBAC

Delivery Manager needs cluster-wide permissions to create K8s resources (ConfigMap, Deployment, Service, Route) in `DEV_NAMESPACE` and `PROD_NAMESPACE` for campaign landing page deployment. The `k8s.yaml` includes:

- **ServiceAccount** `delivery-manager`
- **ClusterRole** `delivery-manager-deployer` — grants CRUD on configmaps, services, deployments, and routes
- **ClusterRoleBinding** `delivery-manager-deployer-binding` — binds the role to the ServiceAccount; set `subjects[0].namespace` to the namespace where delivery-manager is deployed

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8087` | HTTP listen port |
| `MODEL_ENDPOINT` | _(empty)_ | OpenAI-compatible model endpoint |
| `MODEL_NAME` | `qwen3-32b-fp8-dynamic` | Model name for email generation |
| `MODEL_API_KEY` | _(empty, optional)_ | API key for the model endpoint (set via Secret) |
| `CAMPAIGN_API_URL` | `http://localhost:8089` | Campaign API URL for inbox delivery |
| `EVENT_HUB_URL` | `http://localhost:8080` | Event hub URL for status events |
| `CLUSTER_DOMAIN` | `localhost` | OpenShift cluster domain for route URLs |
| `DEV_NAMESPACE` | `marketing-dev` | Namespace for preview deployments |
| `PROD_NAMESPACE` | `marketing-prod` | Namespace for production deployments |
| `APP_NAMESPACE` | `marketing` | Namespace where delivery-manager is deployed |
| `AGENT_ENDPOINT` | _(empty)_ | Public A2A endpoint URL (set in cluster, e.g. `http://delivery-manager:8087`) |
| `LANDING_IMAGE` | `quay.io/rh-ee-dayeo/marketing-assistant:campaign-landing` | Container image for landing pages |
| `LOG_LEVEL` | `INFO` | Python log level |

## Interface

**Protocol:** Google A2A v1.0 (JSON-RPC 2.0)

**Skills:**

| Skill | Description |
|---|---|
| `generate_email` | Generate bilingual (EN/ZH) marketing email content via LLM |
| `deploy_preview` | Deploy a campaign landing page to the dev namespace |
| `deploy_production` | Promote a campaign landing page to the production namespace |
| `send_emails` | Deliver generated emails to target customers via Campaign API |

## Testing

```bash
# 1. Health check
curl http://localhost:8087/healthz

# 2. Agent card
curl http://localhost:8087/.well-known/agent-card.json

# 3. Generate email (bilingual EN/ZH)
curl -s -X POST http://localhost:8087/ \
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
        "parts": [{"text": "{\"skill\":\"generate_email\",\"campaign_name\":\"Summer Retreat\",\"campaign_description\":\"VIP luxury getaway\",\"hotel_name\":\"Simon Resort\",\"campaign_url\":\"https://example.com/summer\",\"target_audience\":\"Platinum members\",\"start_date\":\"2026-07-01\",\"end_date\":\"2026-08-31\"}"}]
      }
    }
  }'

# 4. Deploy preview (mock mode returns local:// URL)
curl -s -X POST http://localhost:8087/ \
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
        "parts": [{"text": "{\"skill\":\"deploy_preview\",\"campaign_id\":\"test-camp-001\",\"html_content\":\"<html><body>Hello</body></html>\"}"}]
      }
    }
  }'

# 5. Deploy production (mock mode returns local:// URL)
curl -s -X POST http://localhost:8087/ \
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
        "parts": [{"text": "{\"skill\":\"deploy_production\",\"campaign_id\":\"test-camp-001\",\"html_content\":\"<html><body>Hello</body></html>\"}"}]
      }
    }
  }'

# 6. Send emails (requires campaign-api on port 8089)
curl -s -X POST http://localhost:8087/ \
  -H "Content-Type: application/json" \
  -H "A2A-Version: 1.0" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "SendMessage",
    "params": {
      "message": {
        "messageId": "test-004",
        "role": "ROLE_USER",
        "parts": [{"text": "{\"skill\":\"send_emails\",\"campaign_id\":\"test-camp-001\",\"customers\":[{\"customer_id\":\"c001\",\"name\":\"Alice\",\"name_en\":\"Alice\",\"email\":\"alice@example.com\",\"tier\":\"Platinum\"}],\"email_subject_en\":\"Summer Retreat\",\"email_body_en\":\"<p>Dear {{customer_name}}, welcome!</p>\",\"email_subject_zh\":\"夏日度假\",\"email_body_zh\":\"<p>亲爱的 {{customer_name}}，欢迎！</p>\"}"}]
      }
    }
  }'
```

Tests 3-5 should return `TASK_STATE_COMPLETED`. Test 6 requires a running campaign-api instance.

## Architecture

```
Campaign Director
       │
       ▼ (A2A)
Delivery Manager
       │
       ├──► LLM            (email generation)
       ├──► K8s API         (deploy preview / production)
       └──► Campaign API    (inbox / email delivery)
```
