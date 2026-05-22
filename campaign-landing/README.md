# Campaign Landing

Express.js server that serves personalized campaign landing pages. This is a **template image** — it is not deployed as a standalone service. Instead, delivery-manager dynamically creates an instance per campaign on OpenShift, injecting each campaign's HTML via ConfigMap.

> Part of [Marketing AI Assistant](../README.md)

## How It Works

```
1. creative-producer generates landing page HTML
2. User clicks "Deploy Preview"
3. delivery-manager calls K8s API:
   ├── Creates ConfigMap (template.html, campaign.json, customers.json)
   ├── Creates Deployment using this image
   ├── Creates Service + Route
   └── Returns route URL
4. Each campaign gets its own Pod running this image
```

When a visitor opens the landing page with `?c=CUSTOMER_ID`, the server fetches the customer profile from MongoDB MCP and personalizes the HTML (name, tier, greeting, etc.).

## Build

Only the container image needs to be built and pushed — delivery-manager references it via `LANDING_IMAGE` setting.

```bash
./build.sh          # defaults to :latest
./build.sh v1.0.0   # or specify a tag
```

## Configuration

These environment variables are set by delivery-manager when creating the Deployment:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3001` | HTTP listen port |
| `DATA_DIR` | `/data` | Mount path for ConfigMap (template.html, campaign.json) |
| `MONGODB_MCP_URL` | `http://mongodb-mcp:8082` | MongoDB MCP server for customer profile lookups |

## API

| Path | Method | Description |
|---|---|---|
| `/` | GET | Serve the landing page. Add `?c=CUSTOMER_ID` for personalized content |
| `/healthz` | GET | Health check |
| `/readyz` | GET | Readiness check (verifies template file exists) |

## Personalization Placeholders

The HTML template can use these placeholders, replaced at request time:

`{{CUSTOMER_NAME}}`, `{{CUSTOMER_FIRST_NAME}}`, `{{CUSTOMER_TIER}}`, `{{CUSTOMER_TIER_BADGE}}`, `{{GREETING}}`, `{{CUSTOMER_INTERESTS}}`, `{{CUSTOMER_LANGUAGE}}`, `{{CAMPAIGN_NAME}}`, `{{HOTEL_NAME}}`

## Local Testing

```bash
npm install

# Prepare test data
mkdir -p /tmp/landing-data
cat > /tmp/landing-data/template.html << 'HTML'
<html><body><h1>{{CAMPAIGN_NAME}}</h1><p>Welcome, {{CUSTOMER_NAME}}!</p></body></html>
HTML
cat > /tmp/landing-data/campaign.json << 'JSON'
{"campaign_name": "Test Campaign", "hotel_name": "Simon Casino Resort"}
JSON

# Start (optionally with mongodb-mcp on port 8082 for personalization)
DATA_DIR=/tmp/landing-data MONGODB_MCP_URL=http://localhost:8082 npm start

# Test
curl http://localhost:3001/healthz
curl http://localhost:3001/
curl "http://localhost:3001/?c=VIP-001"
```

## Project Structure

```
campaign-landing/
├── server.js        # Express app with personalization logic
├── package.json
├── Containerfile
└── build.sh
```
