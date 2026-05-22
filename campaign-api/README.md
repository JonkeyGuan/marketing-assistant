# Campaign API

REST gateway (gunicorn + Flask) that routes campaign operations to the Campaign Director via A2A, enforces guardrails (local regex + Policy Guardian), and serves a fake inbox for email demo.

Part of the [Marketing Assistant](../README.md) multi-agent system.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)

## Project Structure

```
campaign-api/
├── app/
│   ├── __init__.py
│   ├── __main__.py      # Entry point (gunicorn launcher)
│   ├── settings.py      # Environment-based configuration
│   └── server.py        # Flask routes & guardrail enforcement
├── k8s.yaml             # OpenShift manifests (Deployment + Service + ConfigMap)
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
curl http://localhost:8089/healthz
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
oc rollout status deployment/campaign-api -n $NAMESPACE
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `PORT` | Server listen port | `8089` |
| `CAMPAIGN_DIRECTOR_URL` | URL of the Campaign Director A2A agent | -- |
| `POLICY_GUARDIAN_URL` | URL of the Policy Guardian service | -- |
| `EVENT_HUB_URL` | URL of the Event Hub SSE service | -- |
| `LOG_LEVEL` | Logging level | `INFO` |

## Interface

The API exposes REST endpoints consumed by the frontend. Campaign operations are forwarded to the Campaign Director over A2A. Input is validated locally with regex guardrails and optionally via the Policy Guardian before dispatch.

## Testing

```bash
# 1. Health check
curl http://localhost:8089/healthz

# 2. Get available themes
curl http://localhost:8089/api/themes

# 3. Get vertical configuration
curl http://localhost:8089/api/config

# 4. Validate a campaign (regex + Policy Guardian)
curl -s -X POST http://localhost:8089/api/campaigns/validate \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "Summer Retreat",
    "campaign_description": "VIP luxury getaway"
  }'

# 5. Validate a campaign with competitor name (should fail)
curl -s -X POST http://localhost:8089/api/campaigns/validate \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "Beat Jennifer Casino",
    "campaign_description": "Better than the competition"
  }'

# 6. Get inbox emails
curl http://localhost:8089/api/inbox

# 7. Create a campaign (requires Campaign Director on 8088)
curl -s -X POST http://localhost:8089/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "Summer Retreat",
    "campaign_description": "VIP luxury getaway",
    "hotel_name": "Simon Resort",
    "target_audience": "Platinum members",
    "theme": "luxury_gold",
    "start_date": "2026-07-01",
    "end_date": "2026-08-31"
  }'
```

Tests 1-6 can run standalone. Test 7 requires the Campaign Director service.

## Architecture

```
Frontend --> campaign-api --> Campaign Director (A2A) --> downstream agents
                |
                +--> Policy Guardian (guardrails)
```
