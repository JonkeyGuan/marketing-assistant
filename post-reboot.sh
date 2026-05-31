#!/bin/bash
# Reconcile ambient mesh pods after cluster reboot.
#
# CRI-O restores pod sandboxes without re-invoking the CNI plugin chain,
# so ambient pods lose their ztunnel inpod rules (HBONE ports 15001/15006/
# 15008/15053 stop listening). This is a known upstream Istio issue
# (istio/istio#57285) with no configuration-level fix.
#
# This script detects pods missing ztunnel and rollout-restarts their
# Deployments/StatefulSets to force re-enrollment via the CNI plugin.
set -uo pipefail

APP_NS="${NAMESPACE:-marketing}"
PLATFORM_NS="kagenti-system"
TIMEOUT="${TIMEOUT:-180}"

echo "=== Post-Reboot Reconciliation ==="
echo ""

if ! oc whoami &>/dev/null; then
  echo "ERROR: Not logged in to OpenShift. Run 'oc login' first."
  exit 1
fi

# ---------------------------------------------------------------------------
# Detect and restart pods missing ztunnel
# ---------------------------------------------------------------------------
reconcile_namespace() {
  local ns="$1"
  echo "--- Namespace: $ns ---"

  if ! oc get namespace "$ns" &>/dev/null; then
    echo "  Namespace not found, skipping."
    echo ""
    return
  fi

  # Find pods that have ambient annotation but are missing ztunnel port 15008
  local stale_owners=""
  local checked=0
  local broken=0

  while IFS='|' read -r pod_name owner_kind owner_name ambient_annotation; do
    # Skip pods without ambient annotation
    [ "$ambient_annotation" != "enabled" ] && continue
    checked=$((checked + 1))

    # Check if ztunnel port 15008 is listening inside the pod
    local has_ztunnel
    has_ztunnel=$(oc exec "$pod_name" -n "$ns" -- cat /proc/net/tcp 2>/dev/null | \
      awk '{split($2,a,":"); if (strtonum("0x"a[2]) == 15008) print "yes"}' 2>/dev/null | head -1)

    if [ "$has_ztunnel" != "yes" ]; then
      broken=$((broken + 1))
      echo "  ✗ $pod_name — missing ztunnel (owner: $owner_kind/$owner_name)"
      stale_owners="$stale_owners $owner_kind/$owner_name"
    fi
  done < <(oc get pods -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.metadata.ownerReferences[0].kind}{"|"}{.metadata.ownerReferences[0].name}{"|"}{.metadata.annotations.ambient\.istio\.io/redirection}{"\n"}{end}' 2>/dev/null)

  if [ "$checked" -eq 0 ]; then
    echo "  No ambient pods found."
    echo ""
    return
  fi

  if [ "$broken" -eq 0 ]; then
    echo "  All $checked ambient pods have ztunnel — no action needed."
    echo ""
    return
  fi

  echo ""
  echo "  Restarting $broken/$checked affected workloads..."

  # Deduplicate owners and restart
  local restarted=""
  for owner in $stale_owners; do
    # Skip if already restarted
    echo "$restarted" | grep -q "$owner" && continue
    restarted="$restarted $owner"

    local kind="${owner%%/*}"
    local name="${owner##*/}"

    case "$kind" in
      ReplicaSet)
        # Find the Deployment that owns this ReplicaSet
        local dep
        dep=$(oc get rs "$name" -n "$ns" -o jsonpath='{.metadata.ownerReferences[0].name}' 2>/dev/null)
        if [ -n "$dep" ]; then
          echo "  Restarting deployment/$dep..."
          oc rollout restart "deployment/$dep" -n "$ns" 2>/dev/null || true
        fi
        ;;
      StatefulSet)
        echo "  Restarting statefulset/$name..."
        oc rollout restart "statefulset/$name" -n "$ns" 2>/dev/null || true
        ;;
      *)
        echo "  Skipping $owner (unsupported owner kind)"
        ;;
    esac
  done

  # Wait for rollouts
  echo ""
  echo "  Waiting for rollouts..."
  local failed=0
  for owner in $restarted; do
    local kind="${owner%%/*}"
    local name="${owner##*/}"
    local resource=""

    case "$kind" in
      ReplicaSet)
        resource="deployment/$(oc get rs "$name" -n "$ns" -o jsonpath='{.metadata.ownerReferences[0].name}' 2>/dev/null)"
        ;;
      StatefulSet)
        resource="statefulset/$name"
        ;;
    esac

    if [ -n "$resource" ]; then
      if ! oc rollout status "$resource" -n "$ns" --timeout="${TIMEOUT}s" 2>/dev/null; then
        echo "  WARNING: $resource did not become ready within ${TIMEOUT}s"
        failed=$((failed + 1))
      fi
    fi
  done

  if [ "$failed" -gt 0 ]; then
    echo "  Completed with $failed warning(s)"
  else
    echo "  All workloads restarted successfully."
  fi
  echo ""
}

reconcile_namespace "$PLATFORM_NS"
reconcile_namespace "$APP_NS"

# ---------------------------------------------------------------------------
# Restart MCP Gateway broker (reconnect to tools after ztunnel reset)
# ---------------------------------------------------------------------------
MCP_NS="mcp-system"
echo "--- MCP Gateway ---"
if oc get deployment mcp-gateway -n "$MCP_NS" &>/dev/null; then
  echo "  Restarting mcp-gateway broker..."
  oc rollout restart deployment/mcp-gateway -n "$MCP_NS" 2>/dev/null || true
  oc rollout status deployment/mcp-gateway -n "$MCP_NS" --timeout="${TIMEOUT}s" 2>/dev/null || \
    echo "  WARNING: mcp-gateway did not become ready within ${TIMEOUT}s"
else
  echo "  MCP Gateway not found, skipping."
fi
echo ""

echo "=== Reconciliation complete ==="
echo ""
echo "Pod status ($APP_NS):"
oc get pods -n "$APP_NS" --no-headers 2>/dev/null | head -15
echo ""
echo "Pod status ($PLATFORM_NS):"
oc get pods -n "$PLATFORM_NS" --no-headers 2>/dev/null | head -15
