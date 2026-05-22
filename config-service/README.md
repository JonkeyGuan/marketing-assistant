# Config Service

REST API for vertical configuration. Loads industry-specific JSON config files and serves them to all services.

## Port

`8081`

## API

| Endpoint | Description |
|---|---|
| `GET /healthz` | Health check |
| `GET /config` | Full vertical config JSON |
| `GET /config/brand?key=X` | Brand attribute by key |
| `GET /config/prompt?key=X` | Prompt template by key |
| `GET /config/competitors` | Competitor names list |
| `GET /config/seed-data` | MongoDB seed data |
| `GET /config/themes` | Theme definitions |
| `GET /config/properties` | Property names list |
| `GET /config/tiers` | Customer tier definitions |
| `GET /config/presets` | Quick-start campaign presets |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8081` | Server port |
| `VERTICAL_CONFIG` | `hotel-casino` | Vertical ID (matches JSON filename) |
| `VERTICAL_CONFIG_DIR` | `app/verticals` | Directory containing vertical JSON files |

## Vertical Config Files

JSON config files are stored in `app/verticals/` for local development:

```
app/verticals/
├── hotel-casino.json
├── banking.json
├── retail-mall.json
└── telco.json
```

Each file defines: brand identity, properties, customer tiers, themes, competitor names, LLM prompts, quick-start presets, and seed data.

## Local Development

```bash
uv sync
uv run app
```

The default `VERTICAL_CONFIG_DIR=app/verticals` reads config files from the local directory — no extra setup needed.

To switch verticals:

```bash
VERTICAL_CONFIG=banking uv run app
```

## OpenShift Deployment

On OpenShift, vertical config files are **not baked into the image** (excluded via `.containerignore`). Instead, they are mounted as a ConfigMap:

```bash
# Create the ConfigMap from local files
oc create configmap vertical-config \
  --from-file=config-service/app/verticals/ \
  -n $NAMESPACE

# Apply the service manifests
oc apply -f config-service/k8s.yaml -n $NAMESPACE
```

The deployment mounts the `vertical-config` ConfigMap at `/etc/vertical-config`, and the k8s configmap sets `VERTICAL_CONFIG_DIR=/etc/vertical-config`.

To update verticals after editing a JSON file:

```bash
oc create configmap vertical-config \
  --from-file=config-service/app/verticals/ \
  -n $NAMESPACE --dry-run=client -o yaml | oc apply -f -
oc rollout restart deployment/config-service -n $NAMESPACE
```

## Testing

```bash
# Health check
curl http://localhost:8081/healthz

# Full config
curl http://localhost:8081/config | python -m json.tool

# Brand attribute
curl "http://localhost:8081/config/brand?key=company_name"

# Prompt template
curl "http://localhost:8081/config/prompt?key=policy_guardian_intro"

# Competitors
curl http://localhost:8081/config/competitors

# Seed data
curl http://localhost:8081/config/seed-data | python -m json.tool
```
