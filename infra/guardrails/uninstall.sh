#!/bin/bash
# Uninstall TrustyAI guardrails from OpenShift
set -uo pipefail

NAMESPACE="${NAMESPACE:-models}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== TrustyAI Guardrails Uninstall ==="
echo "Namespace: $NAMESPACE"
echo ""
echo "This will remove all guardrails components (detectors, orchestrator, PVCs)."
echo ""

read -p "Continue? [y/N] " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "[1/4] Removing orchestrator..."
for f in "$SCRIPT_DIR"/orchestrator/*.yaml; do
  oc delete -f "$f" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
done

echo "[2/4] Removing detectors and supporting services..."
for f in "$SCRIPT_DIR"/models/*.yaml; do
  oc delete -f "$f" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
done

echo "[3/4] Removing download jobs..."
oc delete job -l app.kubernetes.io/component=guardrails -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
oc delete job download-guardrails-detector-ibm-hap -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
oc delete job download-prompt-injection-detector -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true

echo "[4/4] Removing PVCs..."
oc delete pvc guardrails-detector-ibm-hap -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
oc delete pvc prompt-injection-detector -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true

echo ""
echo "=== Guardrails uninstall complete ==="
echo ""
echo "campaign-api will gracefully skip TrustyAI checks when detectors are unavailable."
echo ""
echo "Usage: NAMESPACE=<ns> $0"
