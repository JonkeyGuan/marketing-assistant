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

# ---------------------------------------------------------------------------
# Phase 1: Helm releases
# ---------------------------------------------------------------------------
echo "[1/5] Uninstalling Helm releases..."

echo "  kagenti..."
helm uninstall kagenti -n "$NAMESPACE" 2>/dev/null || echo "  (not installed)"

echo "  mcp-gateway..."
# Delete CRs before helm uninstall — controller handles finalizer while still running
oc delete mcpgatewayextensions --all -n mcp-system --timeout=30s 2>/dev/null || \
  # Controller already gone? Remove finalizers and force delete
  for mcpgwe in $(oc get mcpgatewayextensions -n mcp-system -o name 2>/dev/null); do
    oc patch "$mcpgwe" -n mcp-system --type=merge -p '{"metadata":{"finalizers":[]}}' 2>/dev/null || true
    oc delete "$mcpgwe" -n mcp-system --ignore-not-found 2>/dev/null || true
  done
helm uninstall mcp-gateway -n mcp-system 2>/dev/null || echo "  (not installed)"

echo "  kagenti-deps..."
helm uninstall kagenti-deps -n "$NAMESPACE" 2>/dev/null || echo "  (not installed)"

# ---------------------------------------------------------------------------
# Phase 2: Operand CRs (must delete before namespaces)
# ---------------------------------------------------------------------------
echo "[2/5] Cleaning up operand CRs..."

# Istio
echo "  Istio..."
oc delete istio default --ignore-not-found 2>/dev/null || true
oc delete istiocni default --ignore-not-found 2>/dev/null || true
oc delete ztunnel default --ignore-not-found 2>/dev/null || true

# SPIRE / Zero Trust Workload Identity Manager — keep operator + workloads intact (faster re-install)
echo "  SPIRE / Zero Trust... (keeping operator)"

# Kuadrant
echo "  Kuadrant..."
oc delete kuadrant --all -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true

# ---------------------------------------------------------------------------
# Phase 3: Cluster-scoped resources
# ---------------------------------------------------------------------------
echo "[3/5] Cleaning up cluster-scoped resources..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
oc delete -f "$SCRIPT_DIR/ambient-reconciler.yaml" --ignore-not-found 2>/dev/null || true

for instance in kagenti kagenti-deps mcp-gateway; do
  oc delete clusterrole,clusterrolebinding -l "app.kubernetes.io/instance=$instance" --ignore-not-found 2>/dev/null || true
done
# MCP Gateway resources without helm labels
for res in $(oc get clusterrole,clusterrolebinding -o name 2>/dev/null | grep mcp-gateway); do
  oc delete "$res" --ignore-not-found 2>/dev/null || true
done

oc delete mutatingwebhookconfiguration,validatingwebhookconfiguration \
  -l app.kubernetes.io/instance=kagenti --ignore-not-found 2>/dev/null || true
oc delete scc kagenti-authbridge --ignore-not-found 2>/dev/null || true

# ---------------------------------------------------------------------------
# Phase 4: Namespaces
# ---------------------------------------------------------------------------
echo "[4/5] Cleaning up namespaces..."

for ns in "$NAMESPACE" "$KC_NAMESPACE" kagenti-agents mcp-system gateway-system; do
  if oc get namespace "$ns" &>/dev/null; then
    echo "  Deleting $ns..."
    oc delete namespace "$ns" --ignore-not-found --timeout=120s 2>/dev/null || \
      echo "  WARNING: $ns did not delete within 120s (may have stuck finalizers)"
  fi
done

# ---------------------------------------------------------------------------
# Phase 5: Verify
# ---------------------------------------------------------------------------
echo "[5/5] Verifying..."

REMAINING=$(oc get namespace "$NAMESPACE" "$KC_NAMESPACE" kagenti-agents mcp-system gateway-system zero-trust-workload-identity-manager 2>/dev/null --no-headers | wc -l)
if [ "$REMAINING" -gt 0 ]; then
  echo "  WARNING: $REMAINING namespace(s) still exist (may be Terminating)"
  oc get namespace "$NAMESPACE" "$KC_NAMESPACE" kagenti-agents mcp-system gateway-system zero-trust-workload-identity-manager 2>/dev/null --no-headers || true
else
  echo "  All namespaces cleaned up."
fi

echo ""
echo "=== Uninstall complete ==="
