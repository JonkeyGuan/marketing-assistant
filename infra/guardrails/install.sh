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
echo "[0/3] Pre-flight checks..."

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
echo "[1/3] Deploying detectors..."

for f in "$SCRIPT_DIR"/models/*.yaml; do
  echo "  $(basename "$f")"
  oc apply -f "$f" -n "$NAMESPACE" 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# Phase 2: Deploy orchestrator
# ---------------------------------------------------------------------------
echo "[2/3] Deploying orchestrator..."

for f in "$SCRIPT_DIR"/orchestrator/*.yaml; do
  echo "  $(basename "$f")"
  oc apply -f "$f" -n "$NAMESPACE" 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# Phase 3: Verify
# ---------------------------------------------------------------------------
echo "[3/3] Waiting for detectors (first run includes model download)..."

echo "  Waiting for HAP detector..."
oc wait --for=condition=Available deployment -l serving.kserve.io/inferenceservice=guardrails-detector-ibm-hap \
  -n "$NAMESPACE" --timeout=600s 2>/dev/null || \
  echo "  WARNING: HAP detector not ready yet. Check: oc logs -l serving.kserve.io/inferenceservice=guardrails-detector-ibm-hap -n $NAMESPACE"

echo "  Waiting for Prompt Injection detector..."
oc wait --for=condition=Available deployment -l serving.kserve.io/inferenceservice=prompt-injection-detector \
  -n "$NAMESPACE" --timeout=600s 2>/dev/null || \
  echo "  WARNING: Prompt Injection detector not ready yet. Check: oc logs -l serving.kserve.io/inferenceservice=prompt-injection-detector -n $NAMESPACE"

echo "  Waiting for Chunker..."
oc wait --for=condition=Available deployment/chunker-service \
  -n "$NAMESPACE" --timeout=120s 2>/dev/null || \
  echo "  WARNING: Chunker not ready yet."

echo ""
echo "Guardrails pods in $NAMESPACE:"
oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -E "guardrails|hap|prompt-injection|chunker|lingua|orchestrator" | head -20
echo ""

echo "=== Guardrails installation complete ==="
echo ""
echo "Services deployed:"
echo "  - HAP Detector (granite-guardian-hap-125m) — PVC 2Gi"
echo "  - Prompt Injection Detector (deberta-v3-base-prompt-injection-v2) — PVC 2Gi"
echo "  - GuardrailsOrchestrator (regex + external detectors)"
echo "  - Chunker + Lingua (supporting services)"
echo ""
echo "Usage: NAMESPACE=<ns> $0"
