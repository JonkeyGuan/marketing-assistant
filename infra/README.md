# Infrastructure Setup

## Installation Order

### 1. OpenShift AI

Install GPU operators and OpenShift AI platform. See [openshift-ai.md](openshift-ai.md) for details.

```bash
# Prerequisites: NFD, NVIDIA GPU Operator, GPU nodes (L40S x3)
# Install operators: cert-manager, Authorino, Service Mesh 3, OpenShift AI 3.x
# Create DataScienceCluster (see openshift-ai.md)
```

### 2. Models

Deploy LLM models via KServe. Models auto-download from HuggingFace on first start, PVCs cache for persistence.

```bash
./models/install.sh                  # default namespace: models
# NAMESPACE=my-ns ./models/install.sh  # custom namespace
```

Models deployed:
- `qwen3-32b-fp8-dynamic` — RedHatAI/Qwen3-32B-FP8-dynamic (50Gi PVC)
- `flux2-klein-4b` — black-forest-labs/FLUX.2-klein-4B (40Gi PVC)
- `qwen3-coder-30b` — Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 (50Gi PVC)

### 3. Guardrails

Deploy TrustyAI guardrails (HAP detector, prompt injection detector, orchestrator).

```bash
./guardrails/install.sh              # default namespace: models
# NAMESPACE=my-ns ./guardrails/install.sh
```

### 4. Kagenti

Install the Kagenti agent platform (Istio ambient mesh, Keycloak, MLflow, etc).

```bash
./kagenti/install.sh
```

## Uninstall (reverse order)

```bash
./kagenti/uninstall.sh
./guardrails/uninstall.sh
./models/uninstall.sh        # PVCs preserved; see script output to delete them
```
