#!/bin/bash
# Install TrustyAI guardrails on OpenShift
# Deploys HAP detector, Prompt Injection detector, and GuardrailsOrchestrator
#
# Each detector pod auto-downloads its model from HuggingFace on first start
# (subsequent restarts skip download if model already exists on PVC).
set -uo pipefail

NAMESPACE="${NAMESPACE:-models}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== TrustyAI Guardrails Installation ==="
echo "Namespace: $NAMESPACE"
echo ""

# ---------------------------------------------------------------------------
# Phase 0: Pre-flight checks
# ---------------------------------------------------------------------------
echo "[0/2] Pre-flight checks..."

if ! oc whoami &>/dev/null; then
  echo "ERROR: Not logged in to OpenShift. Run 'oc login' first."
  exit 1
fi

oc get namespace "$NAMESPACE" &>/dev/null || oc new-project "$NAMESPACE" 2>/dev/null || \
  oc create namespace "$NAMESPACE" 2>/dev/null

echo "  Pre-flight OK"

# ---------------------------------------------------------------------------
# Phase 1: Deploy detectors + supporting services
# ---------------------------------------------------------------------------
echo "[1/2] Deploying detectors..."

for f in "$SCRIPT_DIR"/models/*.yaml; do
  echo "  $(basename "$f")"
  oc apply -f "$f" -n "$NAMESPACE" 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# Phase 2: Deploy orchestrator
# ---------------------------------------------------------------------------
echo "[2/2] Deploying orchestrator..."

for f in "$SCRIPT_DIR"/orchestrator/*.yaml; do
  echo "  $(basename "$f")"
  oc apply -f "$f" -n "$NAMESPACE" 2>/dev/null || true
done

echo ""
echo "=== Guardrails installation complete ==="
echo ""
echo "Usage: NAMESPACE=<ns> $0"
