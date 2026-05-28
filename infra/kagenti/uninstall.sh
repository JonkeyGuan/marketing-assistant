#!/bin/bash
# Uninstall kagenti platform from OpenShift
set -uo pipefail

NAMESPACE="kagenti-system"
KC_NAMESPACE="keycloak"

echo "=== Kagenti Uninstall ==="
echo "This will remove kagenti and kagenti-deps from the cluster."
echo ""

read -p "Continue? [y/N] " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "[1/6] Uninstalling kagenti platform..."
helm uninstall kagenti -n "$NAMESPACE" 2>/dev/null || echo "  (not installed)"

echo "[2/6] Uninstalling MCP Gateway..."
helm uninstall mcp-gateway -n mcp-system 2>/dev/null || echo "  (not installed or skipped)"

echo "[3/6] Uninstalling kagenti-deps..."
helm uninstall kagenti-deps -n "$NAMESPACE" 2>/dev/null || echo "  (not installed)"

echo "[4/6] Cleaning up cluster-scoped resources..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
oc delete -f "$SCRIPT_DIR/ambient-reconciler.yaml" --ignore-not-found 2>/dev/null || true
oc delete clusterrole,clusterrolebinding -l app.kubernetes.io/instance=kagenti --ignore-not-found 2>/dev/null || true
oc delete clusterrole,clusterrolebinding -l app.kubernetes.io/instance=kagenti-deps --ignore-not-found 2>/dev/null || true
oc delete mutatingwebhookconfiguration,validatingwebhookconfiguration -l app.kubernetes.io/instance=kagenti --ignore-not-found 2>/dev/null || true
oc delete scc kagenti-authbridge --ignore-not-found 2>/dev/null || true

echo "[5/6] Cleaning up Istio/SPIRE operand CRs..."
oc delete istio default --ignore-not-found 2>/dev/null || true
oc delete istiocni default --ignore-not-found 2>/dev/null || true
oc delete ztunnel default --ignore-not-found 2>/dev/null || true

echo "[6/6] Cleaning up namespaces..."
for ns in "$NAMESPACE" "$KC_NAMESPACE" kagenti-agents mcp-system gateway-system; do
  oc delete namespace "$ns" --ignore-not-found --timeout=120s 2>/dev/null || true
done

echo ""
echo "=== Uninstall complete ==="
