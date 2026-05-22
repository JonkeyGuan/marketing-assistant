# Event Hub

SSE broadcast service (gunicorn + Flask) that provides real-time progress streaming for campaign workflows. Services publish events, and the frontend subscribes via SSE.

Part of the [Marketing Assistant](../README.md) multi-agent system.

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/)

## Project Structure

```
event-hub/
├── app/
│   ├── __init__.py
│   ├── __main__.py      # Entry point (gunicorn launcher)
│   ├── settings.py      # Environment-based configuration
│   └── server.py        # Flask routes, SSE publish & subscribe
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
curl http://localhost:8080/healthz
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
oc rollout status deployment/event-hub -n $NAMESPACE
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `PORT` | Server listen port | `8080` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Interface

**Publish**: Agents POST events to the hub during workflow execution.

**Subscribe**: The frontend opens an SSE connection to receive real-time progress updates.

## Architecture

```
Agents --> Event Hub (publish) <-- Frontend (SSE subscribe)
           (this service)
```

The Event Hub acts as a central fan-out point. Downstream agents publish progress events as they execute workflow steps. The frontend maintains a persistent SSE connection to stream these updates to the user in real time.
