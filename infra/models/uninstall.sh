#!/bin/bash
# Uninstall LLM models from OpenShift (PVCs are preserved)
set -uo pipefail

NAMESPACE="${NAMESPACE:-models}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS=(qwen3-32b-fp8-dynamic flux2-klein-4b qwen3-coder-30b)

echo "=== Model Uninstall ==="
echo "Namespace: $NAMESPACE"
echo ""
echo "This will remove model InferenceServices, ServingRuntimes, and auth resources."
echo "PVCs are preserved to avoid re-downloading models."
echo ""

read -p "Continue? [y/N] " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "[1/2] Removing models..."
for f in "$SCRIPT_DIR"/*.yaml; do
  oc delete inferenceservice,servingruntime -n "$NAMESPACE" \
    -l opendatahub.io/dashboard=true --ignore-not-found 2>/dev/null || true
done

echo "[2/2] Removing auth resources..."
for MODEL in "${MODELS[@]}"; do
  SA_NAME="${MODEL}-sa"
  oc delete rolebinding "${SA_NAME}-${MODEL}-view" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
  oc delete role "${MODEL}-view" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
  oc delete secret "$SA_NAME" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
  oc delete serviceaccount "$SA_NAME" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
  echo "  $MODEL: auth resources removed"
done

echo ""
echo "PVCs preserved:"
oc get pvc -n "$NAMESPACE" --no-headers 2>/dev/null | head -10
echo ""
echo "To also delete PVCs (and cached models), run:"
echo "  oc delete pvc qwen3-32b-fp8-dynamic flux2-klein-4b qwen3-coder-30b -n $NAMESPACE"
echo ""
echo "=== Model uninstall complete ==="
echo ""
echo "Usage: NAMESPACE=<ns> $0"
