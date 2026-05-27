#!/bin/bash
# Deploy marketing-assistant application to OpenShift + Kagenti
set -uo pipefail

NAMESPACE="${NAMESPACE:-marketing}"
KC_NAMESPACE="keycloak"
KC_REALM="kagenti"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="${DOMAIN:-$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>/dev/null)}"

if [ -z "$DOMAIN" ]; then
  echo "ERROR: Could not detect cluster domain. Set DOMAIN env var manually."
  exit 1
fi

echo "=== Marketing-Assistant Deployment ==="
echo "Cluster domain: $DOMAIN"
echo "Namespace:      $NAMESPACE"
echo ""

# ---------------------------------------------------------------------------
# Phase 0: Pre-flight checks
# ---------------------------------------------------------------------------
echo "[0/4] Pre-flight checks..."

if ! oc whoami &>/dev/null; then
  echo "ERROR: Not logged in to OpenShift. Run 'oc login' first."
  exit 1
fi

if ! helm status kagenti -n kagenti-system &>/dev/null; then
  echo "ERROR: Kagenti platform not installed. Run infra/kagenti/install.sh first."
  exit 1
fi

echo "  Kagenti platform: OK"

# ---------------------------------------------------------------------------
# Phase 1: Create namespace
# ---------------------------------------------------------------------------
echo "[1/4] Creating namespace..."

oc get namespace "$NAMESPACE" &>/dev/null || oc new-project "$NAMESPACE" --display-name="Marketing Assistant" 2>/dev/null || \
  oc create namespace "$NAMESPACE" 2>/dev/null

oc label namespace "$NAMESPACE" kagenti-enabled=true shared-gateway-access=true \
  istio.io/dataplane-mode=ambient istio-discovery=enabled --overwrite 2>/dev/null || true

# Create vertical-config ConfigMap for config-service
echo "  Creating vertical-config ConfigMap..."
oc create configmap vertical-config \
  --from-file="$SCRIPT_DIR/config-service/app/verticals/" \
  -n "$NAMESPACE" --dry-run=client -o yaml | oc apply -f - -n "$NAMESPACE" 2>/dev/null

# Sync authbridge configs from kagenti-agents (needed until marketing is in agentNamespaces)
echo "  Syncing authbridge configs from kagenti-agents..."
for cm in authbridge-config envoy-config spiffe-helper-config; do
  if oc get configmap "$cm" -n kagenti-agents &>/dev/null; then
    oc get configmap "$cm" -n kagenti-agents -o json 2>/dev/null | \
      python3 -c "import sys,json; d=json.load(sys.stdin); d['metadata']={'name':d['metadata']['name'],'namespace':'$NAMESPACE'}; print(json.dumps(d))" | \
      oc apply -f - -n "$NAMESPACE" 2>/dev/null || true
  fi
done

# Fix AuthBridge ISSUER: kagenti-agents ships localtest.me defaults — patch to actual Keycloak route
echo "  Patching AuthBridge config (ISSUER)..."
KC_AB_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$KC_AB_ROUTE" ]; then
  oc patch configmap authbridge-config -n "$NAMESPACE" --type=merge \
    -p "{\"data\":{\"ISSUER\":\"https://${KC_AB_ROUTE}/realms/${KC_REALM}\",\"EXPECTED_AUDIENCE\":\"kagenti\",\"JWT_AUDIENCE\":\"kagenti\"}}" \
    2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Phase 2: Deploy all services
# ---------------------------------------------------------------------------
echo "[2/4] Deploying services..."

SERVICES=(
  mongodb
  config-service
  event-hub
  mongodb-mcp
  imagegen-mcp
  campaign-director
  creative-producer
  customer-analyst
  policy-guardian
  delivery-manager
  campaign-api
  frontend
)

for svc in "${SERVICES[@]}"; do
  if [ -f "$SCRIPT_DIR/$svc/.k8s.yaml" ]; then
    echo "  Applying $svc (.k8s.yaml)..."
    oc apply -f "$SCRIPT_DIR/$svc/.k8s.yaml" -n "$NAMESPACE" 2>/dev/null || true
  elif [ -f "$SCRIPT_DIR/$svc/k8s.yaml" ]; then
    echo "  Applying $svc (k8s.yaml)..."
    oc apply -f "$SCRIPT_DIR/$svc/k8s.yaml" -n "$NAMESPACE" 2>/dev/null || true
  fi
done

# Grant kagenti-authbridge SCC for sidecar injection (after SA resources are created)
echo "  Granting kagenti-authbridge SCC..."
AGENT_SAS=(default campaign-director creative-producer customer-analyst policy-guardian delivery-manager)
for sa in "${AGENT_SAS[@]}"; do
  oc adm policy add-scc-to-user kagenti-authbridge -z "$sa" -n "$NAMESPACE" 2>/dev/null || true
done

# Create marketing-assistant experiment in MLflow (otel-collector routes traces to experiment_id=1)
echo "  Creating MLflow experiment..."
KAGENTI_NS="kagenti-system"
POSTGRES_POD=$(oc get pods -n "$KAGENTI_NS" -l app=postgres-otel -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$POSTGRES_POD" ]; then
  oc exec "$POSTGRES_POD" -n "$KAGENTI_NS" -- psql -U testuser -d mlflow -c "
    INSERT INTO experiments (experiment_id, name, artifact_location, lifecycle_stage, creation_time, last_update_time)
    VALUES (1, 'marketing-assistant', '/mlflow/artifacts/1', 'active',
            EXTRACT(EPOCH FROM NOW())::bigint * 1000, EXTRACT(EPOCH FROM NOW())::bigint * 1000)
    ON CONFLICT (experiment_id) DO UPDATE SET lifecycle_stage = 'active';
  " 2>/dev/null && echo "    done" || echo "    skipped (postgres not ready)"
else
  echo "    skipped (postgres-otel not found)"
fi

# ---------------------------------------------------------------------------
# Phase 3: Keycloak SSO configuration
# ---------------------------------------------------------------------------
echo "[3/4] Configuring Keycloak SSO..."

KC_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
KC_ADMIN_USER=$(oc get secret keycloak-admin -n "$KC_NAMESPACE" -o go-template='{{.data.username | base64decode}}' 2>/dev/null)
KC_ADMIN_PASS=$(oc get secret keycloak-admin -n "$KC_NAMESPACE" -o go-template='{{.data.password | base64decode}}' 2>/dev/null)

if [ -z "$KC_ROUTE" ] || [ -z "$KC_ADMIN_USER" ]; then
  echo "  WARNING: Keycloak not found, skipping SSO configuration."
else
  KC_TOKEN=$(curl -sk -X POST "https://${KC_ROUTE}/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=${KC_ADMIN_USER}" \
    -d "password=${KC_ADMIN_PASS}" \
    -d "grant_type=password" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

  if [ -z "$KC_TOKEN" ]; then
    echo "  WARNING: Could not obtain Keycloak token, skipping SSO configuration."
  else
    KC_REALM_API="https://${KC_ROUTE}/admin/realms/${KC_REALM}"

    # Detect frontend route
    FRONTEND_HOST=$(oc get route frontend -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
    FRONTEND_HOST=${FRONTEND_HOST:-"frontend-${NAMESPACE}.${DOMAIN}"}

    # --- Create marketing-ui client (public, PKCE) ---
    echo "  Creating 'marketing-ui' client..."
    curl -sk -X POST "${KC_REALM_API}/clients" \
      -H "Authorization: Bearer ${KC_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{
        \"clientId\": \"marketing-ui\",
        \"name\": \"Marketing Assistant Dashboard\",
        \"enabled\": true,
        \"publicClient\": true,
        \"standardFlowEnabled\": true,
        \"directAccessGrantsEnabled\": false,
        \"rootUrl\": \"https://${FRONTEND_HOST}\",
        \"redirectUris\": [\"https://${FRONTEND_HOST}/*\"],
        \"webOrigins\": [\"https://${FRONTEND_HOST}\"],
        \"attributes\": {
          \"pkce.code.challenge.method\": \"S256\"
        }
      }" 2>/dev/null > /dev/null
    echo "    done"

    # --- Add audience mapper so tokens carry aud=kagenti (required by AuthBridge) ---
    echo "  Adding audience mapper to marketing-ui..."
    MKT_CLI_UUID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
      "${KC_REALM_API}/clients?clientId=marketing-ui" 2>/dev/null | \
      python3 -c "import sys,json; c=json.load(sys.stdin); print(c[0]['id'] if c else '')" 2>/dev/null || echo "")
    if [ -n "$MKT_CLI_UUID" ]; then
      curl -sk -X POST "${KC_REALM_API}/clients/${MKT_CLI_UUID}/protocol-mappers/models" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
          "name": "kagenti-audience",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "config": {
            "included.custom.audience": "kagenti",
            "id.token.claim": "true",
            "access.token.claim": "true"
          }
        }' 2>/dev/null > /dev/null
      echo "    done"
    fi

    # --- Create demo users ---
    echo "  Creating demo users..."
    for KC_USER_DATA in "alice:alice:Alice:Chen:Senior Marketing Executive" "bob:bob:Bob:Santos:Junior Marketing Associate"; do
      KC_UNAME=$(echo "$KC_USER_DATA" | cut -d: -f1)
      KC_UPASS=$(echo "$KC_USER_DATA" | cut -d: -f2)
      KC_FIRST=$(echo "$KC_USER_DATA" | cut -d: -f3)
      KC_LAST=$(echo "$KC_USER_DATA" | cut -d: -f4)

      curl -sk -X POST "${KC_REALM_API}/users" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
          \"username\": \"${KC_UNAME}\",
          \"enabled\": true,
          \"firstName\": \"${KC_FIRST}\",
          \"lastName\": \"${KC_LAST}\",
          \"email\": \"${KC_UNAME}@example.com\",
          \"emailVerified\": true,
          \"credentials\": [{
            \"type\": \"password\",
            \"value\": \"${KC_UPASS}\",
            \"temporary\": false
          }]
        }" 2>/dev/null > /dev/null

      KC_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
        "${KC_REALM_API}/users?username=${KC_UNAME}&exact=true" 2>/dev/null | \
        python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
      if [ -n "$KC_UID" ]; then
        curl -sk -X PUT "${KC_REALM_API}/users/${KC_UID}/reset-password" \
          -H "Authorization: Bearer ${KC_TOKEN}" \
          -H "Content-Type: application/json" \
          -d "{\"type\":\"password\",\"value\":\"${KC_UPASS}\",\"temporary\":false}" 2>/dev/null > /dev/null
      fi
      echo "    ${KC_UNAME} / ${KC_UPASS}"
    done

    # --- Create realm roles ---
    echo "  Creating realm roles..."
    for ROLE_DEF in "kagenti-viewer:View agents and tools in KAgenti UI" "platinum-access:Access to platinum-tier customer data"; do
      ROLE_NAME=${ROLE_DEF%%:*}; ROLE_DESC=${ROLE_DEF#*:}
      curl -sk -X POST "${KC_REALM_API}/roles" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${ROLE_NAME}\",\"description\":\"${ROLE_DESC}\"}" 2>/dev/null > /dev/null
      echo "    ${ROLE_NAME}"
    done

    # --- Assign roles to users ---
    echo "  Assigning roles..."
    ADMIN_ROLE=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" "${KC_REALM_API}/roles/admin" 2>/dev/null)
    VIEWER_ROLE=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" "${KC_REALM_API}/roles/kagenti-viewer" 2>/dev/null)
    PLAT_ROLE=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" "${KC_REALM_API}/roles/platinum-access" 2>/dev/null)

    for KC_ROLE_USER in alice bob admin; do
      KC_ROLE_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
        "${KC_REALM_API}/users?username=${KC_ROLE_USER}&exact=true" 2>/dev/null | \
        python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
      if [ -n "$KC_ROLE_UID" ]; then
        curl -sk -X POST "${KC_REALM_API}/users/${KC_ROLE_UID}/role-mappings/realm" \
          -H "Authorization: Bearer ${KC_TOKEN}" \
          -H "Content-Type: application/json" \
          -d "[${ADMIN_ROLE},${VIEWER_ROLE}]" 2>/dev/null > /dev/null
        echo "    ${KC_ROLE_USER}: admin, kagenti-viewer"
      fi
    done

    # Only alice gets platinum-access
    ALICE_ID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
      "${KC_REALM_API}/users?username=alice&exact=true" 2>/dev/null | \
      python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
    if [ -n "$ALICE_ID" ]; then
      curl -sk -X POST "${KC_REALM_API}/users/${ALICE_ID}/role-mappings/realm" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "[${PLAT_ROLE}]" 2>/dev/null > /dev/null
      echo "    alice: + platinum-access"
    fi
    echo "    (bob does NOT have platinum-access)"

    # --- Add users to MLflow groups (required by mlflow-oidc plugin) ---
    echo "  Adding users to MLflow groups..."
    MLFLOW_ADMIN_GID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
      "${KC_REALM_API}/groups?search=mlflow-admin" 2>/dev/null | \
      python3 -c "import sys,json; g=json.load(sys.stdin); print(g[0]['id'] if g else '')" 2>/dev/null || echo "")
    if [ -n "$MLFLOW_ADMIN_GID" ]; then
      for KC_MLF_USER in admin alice bob; do
        KC_MLF_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
          "${KC_REALM_API}/users?username=${KC_MLF_USER}&exact=true" 2>/dev/null | \
          python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
        if [ -n "$KC_MLF_UID" ]; then
          curl -sk -X PUT "${KC_REALM_API}/users/${KC_MLF_UID}/groups/${MLFLOW_ADMIN_GID}" \
            -H "Authorization: Bearer ${KC_TOKEN}" -H "Content-Type: application/json" -d '{}' 2>/dev/null
          echo "    ${KC_MLF_USER}: mlflow-admin"
        fi
      done
    else
      echo "    skipped (mlflow-admin group not found)"
    fi

    # --- Update frontend-keycloak-config ConfigMap ---
    echo "  Patching frontend-keycloak-config..."
    oc create configmap frontend-keycloak-config -n "$NAMESPACE" \
      --from-literal="keycloak-config.js=window.__KEYCLOAK_URL__ = \"https://${KC_ROUTE}\";
window.__KEYCLOAK_REALM__ = \"${KC_REALM}\";
window.__KEYCLOAK_CLIENT_ID__ = \"marketing-ui\";" \
      --dry-run=client -o yaml | oc apply -f - -n "$NAMESPACE" 2>/dev/null
    echo "    done"

    # Restart frontend to pick up new config
    oc rollout restart deployment/frontend -n "$NAMESPACE" 2>/dev/null || true

    echo ""
    echo "  SSO configured:"
    echo "    Client: marketing-ui (public, PKCE)"
    echo "    Users: alice/alice (platinum), bob/bob (no platinum), admin (from install.sh)"
    echo "    Roles: admin, kagenti-viewer (all), platinum-access (alice only)"
  fi
fi

# ---------------------------------------------------------------------------
# Phase 4: Verify
# ---------------------------------------------------------------------------
echo "[4/4] Verifying deployment..."
echo ""
echo "Pods in $NAMESPACE:"
oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | head -20
echo ""

FRONTEND_ROUTE=$(oc get route frontend -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
echo "=== Deployment complete ==="
echo ""
echo "Routes:"
oc get routes -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{printf "  %-15s https://%s\n", $1, $2}'
echo ""
if [ -n "$FRONTEND_ROUTE" ]; then
  echo "Frontend: https://${FRONTEND_ROUTE}"
fi
echo ""
echo "Keycloak: https://$(oc get route keycloak -n $KC_NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null)"
