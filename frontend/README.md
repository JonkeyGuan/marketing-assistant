# Frontend

React single-page application for the Campaign Manager dashboard. Provides a campaign creation wizard with theme selection, real-time agent progress via SSE, email preview, and a fake inbox.

> Part of [Marketing AI Assistant](../README.md)

## Prerequisites

- Node.js 18+
- npm
- Podman (for container builds)

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── index.tsx                          # React entry point
│   ├── App.tsx                            # Router & top-level layout
│   ├── pages/
│   │   ├── Dashboard.tsx                  # Campaign overview
│   │   ├── CampaignCreate.tsx             # Campaign creation wizard
│   │   └── Inbox.tsx                      # Fake email inbox
│   ├── components/
│   │   ├── Layout/Layout.tsx              # App shell / navigation
│   │   ├── CampaignWizard/CampaignWizard.tsx
│   │   ├── PreviewPanel/PreviewPanel.tsx
│   │   └── WorkflowNavigator/WorkflowNavigator.tsx
│   ├── auth/
│   │   ├── authFetch.ts                   # Authenticated fetch wrapper
│   │   └── KeycloakProvider.tsx
│   └── config/
│       └── VerticalConfigProvider.tsx     # Vertical/theme configuration
├── k8s.yaml                              # OpenShift manifests
├── package.json
├── tsconfig.json
└── build.sh
```

## Local Development

```bash
# Install dependencies
npm install

# Start the dev server (proxies API calls to campaign-api on localhost:8089)
npm start

# Open in browser
open http://localhost:3000
```

## Build & Deploy to OpenShift

```bash
# Build and push the container image (multi-stage: npm build + nginx)
./build.sh          # defaults to :latest
./build.sh v1.0.0   # or specify a tag

# Apply manifests
oc apply -f k8s.yaml

# Verify the deployment
oc rollout status deployment/frontend
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `proxy` (package.json) | `http://localhost:8089` | Dev-mode API proxy target (campaign-api) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (production ConfigMap) |

In production the Containerfile builds static assets and serves them with nginx on port 8080. The nginx configuration proxies `/api` requests to campaign-api.

## Key Features

- **Campaign Wizard** -- step-by-step campaign creation with theme selection (luxury_gold, festive_red, modern_black, classic_emerald)
- **Real-time Progress** -- SSE stream shows live agent workflow status
- **Email Preview** -- preview generated marketing emails before sending
- **Inbox** -- simulated customer inbox to view delivered emails
- **Vertical Config** -- pluggable branding/vertical configuration via `VerticalConfigProvider`

## Architecture

```
Browser               Frontend (React)         campaign-api        Campaign Director
                      (this service)           (REST gateway)      & Agents
   │                       │                        │                    │
   │  http://host:3000     │                        │                    │
   ├──────────────────────►│                        │                    │
   │                       │  /api/* (proxy)        │                    │
   │                       ├───────────────────────►│   A2A calls        │
   │                       │                        ├───────────────────►│
   │                       │                        │   SSE progress     │
   │                       │  SSE stream            │◄───────────────────┤
   │◄──────────────────────┤◄───────────────────────┤                    │
   │                       │                        │                    │
```
