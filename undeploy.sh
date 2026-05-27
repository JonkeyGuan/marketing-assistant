#!/bin/bash
# Remove marketing-assistant application from OpenShift
set -uo pipefail

NAMESPACE="${NAMESPACE:-marketing}"
KC_NAMESPACE="keycloak"
KC_REALM="kagenti"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Marketing-Assistant Uninstall ==="
echo "Namespace: $NAMESPACE"
echo ""

read -p "Continue? [y/N] " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

# ---------------------------------------------------------------------------
# Phase 1: Delete application resources
# ---------------------------------------------------------------------------
echo "[1/3] Removing application resources..."

SERVICES=(
  frontend
  campaign-api
  delivery-manager
  policy-guardian
  customer-analyst
  creative-producer
  campaign-director
  imagegen-mcp
  mongodb-mcp
  event-hub
  config-service
  mongodb
)

for svc in "${SERVICES[@]}"; do
  if [ -f "$SCRIPT_DIR/$svc/.k8s.yaml" ]; then
    echo "  Deleting $svc..."
    oc delete -f "$SCRIPT_DIR/$svc/.k8s.yaml" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
  elif [ -f "$SCRIPT_DIR/$svc/k8s.yaml" ]; then
    echo "  Deleting $svc..."
    oc delete -f "$SCRIPT_DIR/$svc/k8s.yaml" -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true
  fi
done

# Delete vertical-config ConfigMap
echo "  Deleting vertical-config ConfigMap..."
oc delete configmap vertical-config -n "$NAMESPACE" --ignore-not-found 2>/dev/null || true

# ---------------------------------------------------------------------------
# Phase 2: Clean up Keycloak resources
# ---------------------------------------------------------------------------
echo "[2/3] Cleaning up Keycloak..."

KC_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
KC_ADMIN_USER=$(oc get secret keycloak-admin -n "$KC_NAMESPACE" -o go-template='{{.data.username | base64decode}}' 2>/dev/null)
KC_ADMIN_PASS=$(oc get secret keycloak-admin -n "$KC_NAMESPACE" -o go-template='{{.data.password | base64decode}}' 2>/dev/null)

if [ -n "$KC_ROUTE" ] && [ -n "$KC_ADMIN_USER" ]; then
  KC_TOKEN=$(curl -sk -X POST "https://${KC_ROUTE}/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=${KC_ADMIN_USER}" \
    -d "password=${KC_ADMIN_PASS}" \
    -d "grant_type=password" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

  if [ -n "$KC_TOKEN" ]; then
    KC_REALM_API="https://${KC_ROUTE}/admin/realms/${KC_REALM}"

    # Delete marketing-ui client
    CLIENT_ID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
      "${KC_REALM_API}/clients?clientId=marketing-ui" 2>/dev/null | \
      python3 -c "import sys,json; c=json.load(sys.stdin); print(c[0]['id'] if c else '')" 2>/dev/null || echo "")
    if [ -n "$CLIENT_ID" ]; then
      curl -sk -X DELETE "${KC_REALM_API}/clients/${CLIENT_ID}" \
        -H "Authorization: Bearer ${KC_TOKEN}" 2>/dev/null
      echo "  Deleted client: marketing-ui"
    fi

    # Delete demo users (alice, bob)
    for DEL_USER in alice bob; do
      DEL_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
        "${KC_REALM_API}/users?username=${DEL_USER}&exact=true" 2>/dev/null | \
        python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
      if [ -n "$DEL_UID" ]; then
        curl -sk -X DELETE "${KC_REALM_API}/users/${DEL_UID}" \
          -H "Authorization: Bearer ${KC_TOKEN}" 2>/dev/null
        echo "  Deleted user: ${DEL_USER}"
      fi
    done

    # Delete roles
    for DEL_ROLE in platinum-access kagenti-viewer; do
      curl -sk -X DELETE "${KC_REALM_API}/roles/${DEL_ROLE}" \
        -H "Authorization: Bearer ${KC_TOKEN}" 2>/dev/null && \
        echo "  Deleted role: ${DEL_ROLE}" || true
    done
  else
    echo "  WARNING: Could not obtain Keycloak token, skipping cleanup."
  fi
else
  echo "  Keycloak not found, skipping."
fi

# ---------------------------------------------------------------------------
# Phase 3: Delete namespace
# ---------------------------------------------------------------------------
echo "[3/3] Deleting namespace..."
oc delete namespace "$NAMESPACE" --ignore-not-found --timeout=120s 2>/dev/null || true

echo ""
echo "=== Uninstall complete ==="
