#!/bin/bash
# Install kagenti platform on OpenShift
# Reference: https://github.com/kagenti/kagenti/blob/main/scripts/ocp/setup-kagenti.sh
set -euo pipefail

NAMESPACE="kagenti-system"
KC_NAMESPACE="keycloak"
MCP_NAMESPACE="mcp-system"
CHART_VERSION="${CHART_VERSION:-0.6.0-rc.6}"
MCP_GW_VERSION="${MCP_GW_VERSION:-0.4.1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="${DOMAIN:-$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')}"

if [ -z "$DOMAIN" ]; then
  echo "ERROR: Could not detect cluster domain. Set DOMAIN env var manually."
  exit 1
fi

echo "=== Kagenti Installation ==="
echo "Cluster domain: $DOMAIN"
echo "Chart version:  $CHART_VERSION"
echo "Namespace:      $NAMESPACE"
echo ""

# ---------------------------------------------------------------------------
# Phase 0: Pre-flight — adopt existing namespaces, OVN
# ---------------------------------------------------------------------------
echo "[0/9] Pre-flight checks..."

echo "  Labeling namespaces for Helm adoption..."
for ns in istio-system gateway-system; do
  if oc get namespace "$ns" &>/dev/null; then
    oc label namespace "$ns" app.kubernetes.io/managed-by=Helm --overwrite 2>/dev/null || true
    oc annotate namespace "$ns" \
      meta.helm.sh/release-name=kagenti-deps \
      meta.helm.sh/release-namespace="$NAMESPACE" \
      --overwrite 2>/dev/null || true
  fi
done

echo "  Enabling OVN local gateway mode for Istio Ambient..."
CURRENT_ROUTING=$(oc get network.operator.openshift.io cluster \
  -o jsonpath='{.spec.defaultNetwork.ovnKubernetesConfig.gatewayConfig.routingViaHost}' 2>/dev/null)
if [ "$CURRENT_ROUTING" != "true" ]; then
  oc patch network.operator.openshift.io cluster --type=merge \
    -p '{"spec":{"defaultNetwork":{"ovnKubernetesConfig":{"gatewayConfig":{"routingViaHost":true}}}}}' 2>/dev/null || true
  echo "  OVN patched — nodes will roll (MCP update)."
else
  echo "  OVN routingViaHost already enabled."
fi

# ---------------------------------------------------------------------------
# Phase 1: Install kagenti-deps (Keycloak, MLflow, Istio, OTEL, SPIRE)
# ---------------------------------------------------------------------------
echo "[1/9] Installing kagenti-deps..."

if helm status kagenti-deps -n "$NAMESPACE" &>/dev/null; then
  echo "  kagenti-deps already installed, upgrading..."
  helm upgrade kagenti-deps oci://ghcr.io/kagenti/kagenti/kagenti-deps \
    --version "$CHART_VERSION" \
    -n "$NAMESPACE" \
    --reset-values \
    -f "$SCRIPT_DIR/values-deps.yaml" \
    --set "domain=$DOMAIN" \
    --set "keycloak.publicUrl=https://keycloak.$DOMAIN" \
    --set "spire.trustDomain=${DOMAIN}" \
    --no-hooks \
    --timeout 20m
else
  helm install kagenti-deps oci://ghcr.io/kagenti/kagenti/kagenti-deps \
    --version "$CHART_VERSION" \
    --create-namespace -n "$NAMESPACE" \
    -f "$SCRIPT_DIR/values-deps.yaml" \
    --set "domain=$DOMAIN" \
    --set "keycloak.publicUrl=https://keycloak.$DOMAIN" \
    --set "spire.trustDomain=${DOMAIN}" \
    --no-hooks \
    --timeout 20m
fi

# ---------------------------------------------------------------------------
# Phase 2: Wait for operators and CRDs, SPIRE SCC
# ---------------------------------------------------------------------------
echo "[2/9] Waiting for operators..."

echo "  Waiting for cert-manager..."
oc wait --for=condition=Available deployment -l app.kubernetes.io/name=cert-manager \
  -n cert-manager --timeout=300s 2>/dev/null || true

echo "  Waiting for RHBK operator..."
oc wait --for=condition=Available deployment/rhbk-operator \
  -n "$KC_NAMESPACE" --timeout=300s 2>/dev/null || \
  oc wait --for=condition=Available deployment -l app.kubernetes.io/name=rhbk-operator \
  -n "$KC_NAMESPACE" --timeout=300s 2>/dev/null || true

echo "  Waiting for Keycloak CRD..."
timeout=300
elapsed=0
while ! oc get crd keycloaks.k8s.keycloak.org &>/dev/null; do
  if [ "$elapsed" -ge "$timeout" ]; then
    echo "  WARNING: Keycloak CRD not found after ${timeout}s, continuing..."
    break
  fi
  sleep 5
  elapsed=$((elapsed + 5))
done

echo "  Waiting for PostgreSQL (Keycloak)..."
oc wait --for=condition=Ready pod -l app=postgres-kc \
  -n "$KC_NAMESPACE" --timeout=300s 2>/dev/null || true

# ---------------------------------------------------------------------------
# SPIRE SCC fix (OpenShift requires privileged SCC)
echo "  Granting SPIRE privileged SCC..."
SPIRE_NS="zero-trust-workload-identity-manager"
oc adm policy add-scc-to-user privileged -z spire-agent -n "$SPIRE_NS" 2>/dev/null || true
oc adm policy add-scc-to-user privileged -z spire-spiffe-csi-driver -n "$SPIRE_NS" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Phase 3: Apply deps hook resources (operand CRs — Keycloak CR, Istio CR, etc.)
# ---------------------------------------------------------------------------
echo "[3/9] Applying deps operand CRs..."

HOOKS_RAW=$(helm get hooks kagenti-deps -n "$NAMESPACE" 2>/dev/null || true)
if [ -n "$HOOKS_RAW" ]; then
  echo "$HOOKS_RAW" | python3 -c "
import yaml, sys
for doc in yaml.safe_load_all(sys.stdin):
    if not doc or not isinstance(doc, dict) or 'kind' not in doc:
        continue
    ann = doc.get('metadata', {}).get('annotations', {})
    for k in list(ann):
        if 'helm.sh/hook' in k:
            del ann[k]
    print('---')
    yaml.dump(doc, sys.stdout, default_flow_style=False)
" | oc apply -f - 2>/dev/null || true
fi

echo "  Waiting for Keycloak to become ready..."
oc wait --for=condition=Ready pod -l app=keycloak \
  -n "$KC_NAMESPACE" --timeout=600s 2>/dev/null || \
  echo "  WARNING: Keycloak pods not ready yet, continuing..."

# ---------------------------------------------------------------------------
# Sync Istio CA (pre-existing OSSM CA takes precedence)
# ---------------------------------------------------------------------------
# When OSSM (openshift-gateway Istio) is already installed, it owns the
# istio-ca-root-cert configmap. Kagenti's istiod in istio-system must use the
# same CA, otherwise ztunnel cert verification fails with BadSignature.
if oc get secret istio-ca-secret -n openshift-ingress &>/dev/null; then
  echo "  Syncing Istio CA from openshift-ingress to istio-system..."
  oc get secret istio-ca-secret -n openshift-ingress -o json 2>/dev/null | \
    python3 -c "
import json, sys
s = json.load(sys.stdin)
s['metadata'] = {'name': 'istio-ca-secret', 'namespace': 'istio-system'}
json.dump(s, sys.stdout)
" | oc apply -f - 2>/dev/null || true

  echo "  Waiting for istiod..."
  oc wait --for=condition=Available deployment/istiod -n istio-system --timeout=120s 2>/dev/null || true
  oc rollout restart deployment/istiod -n istio-system 2>/dev/null || true
  sleep 10
  oc delete pods -n istio-ztunnel -l app=ztunnel 2>/dev/null || true
  echo "  Waiting for ztunnel pods..."
  sleep 15
fi

# Ensure Kiali CR exists (may be skipped by YAML parser during hook apply)
KIALI_COUNT=$(oc get kiali -n istio-system --no-headers 2>/dev/null | wc -l)
if oc get crd kialis.kiali.io &>/dev/null && [ "$KIALI_COUNT" -eq 0 ]; then
  echo "  Applying Kiali CR..."
  helm get hooks kagenti-deps -n "$NAMESPACE" 2>/dev/null | python3 -c "
import yaml, sys
for doc in yaml.safe_load_all(sys.stdin):
    if not doc or not isinstance(doc, dict) or doc.get('kind') != 'Kiali':
        continue
    ann = doc.get('metadata', {}).get('annotations', {})
    for k in list(ann):
        if 'helm.sh/hook' in k:
            del ann[k]
    print('---')
    yaml.dump(doc, sys.stdout, default_flow_style=False)
" | oc apply -f - 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Phase 4: Install MCP Gateway
# ---------------------------------------------------------------------------
echo "[4/9] Installing MCP Gateway..."
if helm status mcp-gateway -n "$MCP_NAMESPACE" &>/dev/null; then
  helm upgrade mcp-gateway oci://ghcr.io/kagenti/charts/mcp-gateway \
    --version "$MCP_GW_VERSION" \
    -n "$MCP_NAMESPACE" \
    --reset-values \
    --set "image.tag=v${MCP_GW_VERSION}" \
    --timeout 5m
else
  helm install mcp-gateway oci://ghcr.io/kagenti/charts/mcp-gateway \
    --version "$MCP_GW_VERSION" \
    --create-namespace -n "$MCP_NAMESPACE" \
    --set "image.tag=v${MCP_GW_VERSION}" \
    --timeout 5m
fi

# ---------------------------------------------------------------------------
# Phase 5: Install kagenti platform
# ---------------------------------------------------------------------------
echo "[5/9] Installing kagenti platform..."

if helm status kagenti -n "$NAMESPACE" &>/dev/null; then
  echo "  kagenti already installed, upgrading..."
  helm upgrade kagenti oci://ghcr.io/kagenti/kagenti/kagenti \
    --version "$CHART_VERSION" \
    -n "$NAMESPACE" \
    --reset-values \
    -f "$SCRIPT_DIR/values-kagenti.yaml" \
    --set "domain=$DOMAIN" \
    --set "agentOAuthSecret.spiffePrefix=spiffe://${DOMAIN}/sa" \
    --set "agentOAuthSecret.useServiceAccountCA=false" \
    --set "uiOAuthSecret.useServiceAccountCA=false" \
    --no-hooks \
    --timeout 10m
else
  helm install kagenti oci://ghcr.io/kagenti/kagenti/kagenti \
    --version "$CHART_VERSION" \
    -n "$NAMESPACE" \
    -f "$SCRIPT_DIR/values-kagenti.yaml" \
    --set "domain=$DOMAIN" \
    --set "agentOAuthSecret.spiffePrefix=spiffe://${DOMAIN}/sa" \
    --set "agentOAuthSecret.useServiceAccountCA=false" \
    --set "uiOAuthSecret.useServiceAccountCA=false" \
    --no-hooks \
    --timeout 10m
fi

# ---------------------------------------------------------------------------
# Phase 6: Apply kagenti chart hooks (skipped by --no-hooks)
# ---------------------------------------------------------------------------
echo "[6/9] Applying kagenti hook resources..."
KAGENTI_HOOKS=$(helm get hooks kagenti -n "$NAMESPACE" 2>/dev/null || true)
if [ -n "$KAGENTI_HOOKS" ]; then
  echo "$KAGENTI_HOOKS" | python3 -c "
import yaml, sys
for doc in yaml.safe_load_all(sys.stdin):
    if not doc or not isinstance(doc, dict) or 'kind' not in doc:
        continue
    ann = doc.get('metadata', {}).get('annotations', {})
    for k in list(ann):
        if 'helm.sh/hook' in k:
            del ann[k]
    print('---')
    yaml.dump(doc, sys.stdout, default_flow_style=False)
" | oc apply -f - 2>/dev/null || true
fi

echo "  Waiting for route processor job..."
oc wait --for=condition=Complete job/kagenti-process-routes-job \
  -n "$NAMESPACE" --timeout=120s 2>/dev/null || true

# Ensure kagenti-ui-config exists (route processor job may fail on first install)
if ! oc get configmap kagenti-ui-config -n "$NAMESPACE" &>/dev/null; then
  echo "  Creating kagenti-ui-config (route processor fallback)..."
  API_ROUTE=$(oc get route kagenti-api -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
  KC_UI_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
  MLFLOW_ROUTE=$(oc get route mlflow -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
  KIALI_ROUTE=$(oc get route kiali -n istio-system -o jsonpath='{.spec.host}' 2>/dev/null)
  oc create configmap kagenti-ui-config -n "$NAMESPACE" \
    --from-literal=DOMAIN_NAME="$DOMAIN" \
    --from-literal=API_URL="https://${API_ROUTE}" \
    --from-literal=KEYCLOAK_CONSOLE_URL="https://${KC_UI_ROUTE}" \
    --from-literal=MLFLOW_DASHBOARD_URL="https://${MLFLOW_ROUTE}" \
    --from-literal=MCP_INSPECTOR_URL="" \
    --from-literal=MCP_PROXY_FULL_ADDRESS="" \
    --from-literal=NETWORK_DASHBOARD_URL="https://${KIALI_ROUTE}" \
    2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Phase 7: Post-install fixups
# ---------------------------------------------------------------------------
echo "[7/9] Applying post-install fixups..."

# Fix Kiali URL in kagenti-ui-config (route processor doesn't know about Kiali)
echo "  Patching Kiali URL in UI config..."
KIALI_ROUTE=$(oc get route kiali -n istio-system -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$KIALI_ROUTE" ]; then
  oc patch configmap kagenti-ui-config -n "$NAMESPACE" --type=merge \
    -p "{\"data\":{\"NETWORK_DASHBOARD_URL\":\"https://${KIALI_ROUTE}\"}}" 2>/dev/null || true
fi

# Fix MLflow OIDC: discovery URL must use external Keycloak route (not internal svc)
echo "  Patching MLflow OIDC discovery URL..."
KC_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$KC_ROUTE" ]; then
  oc patch secret mlflow-oauth-secret -n "$NAMESPACE" --type='json' \
    -p="[{\"op\":\"replace\",\"path\":\"/data/OIDC_DISCOVERY_URL\",\"value\":\"$(echo -n "https://${KC_ROUTE}/realms/kagenti/.well-known/openid-configuration" | base64)\"}]" \
    2>/dev/null || true
fi

# Fix MLflow probes: chart defaults hit /version which returns 401 with auth enabled
echo "  Patching MLflow probes..."
oc patch deployment mlflow -n "$NAMESPACE" --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/health"},
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/health"}
]' 2>/dev/null || true

# Persist MLflow artifacts: replace emptyDir with PVC (RWO)
echo "  Persisting MLflow artifacts..."
if ! oc get pvc mlflow-artifacts -n "$NAMESPACE" &>/dev/null; then
  oc apply -f - <<'PVCEOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mlflow-artifacts
  namespace: kagenti-system
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
PVCEOF
fi
oc patch deployment mlflow -n "$NAMESPACE" --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/volumes/0","value":{"name":"mlflow-artifacts","persistentVolumeClaim":{"claimName":"mlflow-artifacts"}}}
]' 2>/dev/null || true

# Fix AuthBridge config: replace localtest.me defaults with actual Keycloak URLs
echo "  Patching AuthBridge config..."
KC_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
if [ -n "$KC_ROUTE" ]; then
  oc patch configmap authbridge-config -n "$NAMESPACE" --type=merge \
    -p "{\"data\":{\"ISSUER\":\"https://${KC_ROUTE}/realms/kagenti\",\"EXPECTED_AUDIENCE\":\"kagenti-ui\",\"JWT_AUDIENCE\":\"kagenti-ui\",\"KEYCLOAK_URL\":\"http://keycloak.keycloak.svc.cluster.local:8080\",\"TOKEN_URL\":\"http://keycloak.keycloak.svc.cluster.local:8080/realms/kagenti/protocol/openid-connect/token\"}}" \
    2>/dev/null || true
fi

# Fix kagenti-manager-role: add list/watch for serviceaccounts (chart only ships create/get/update)
echo "  Patching kagenti-manager-role (serviceaccounts list/watch)..."
oc get clusterrole kagenti-manager-role -o json 2>/dev/null | python3 -c "
import sys, json
role = json.load(sys.stdin)
for rule in role.get('rules', []):
    if 'serviceaccounts' in rule.get('resources', []):
        verbs = set(rule.get('verbs', []))
        verbs.update(['list', 'watch'])
        rule['verbs'] = sorted(verbs)
del role['metadata']['resourceVersion']
del role['metadata']['uid']
del role['metadata']['creationTimestamp']
role['metadata'].pop('managedFields', None)
json.dump(role, sys.stdout)
" | oc apply -f - 2>/dev/null || true

# Restart controller-manager to pick up new RBAC
oc rollout restart deployment/kagenti-controller-manager -n "$NAMESPACE" 2>/dev/null || true
oc wait --for=condition=Available deployment/kagenti-controller-manager \
  -n "$NAMESPACE" --timeout=60s 2>/dev/null || true

# MLflow trace-name trigger: OTLP ingest doesn't set mlflow.traceName tag (fixed in v3.13+)
# Must run AFTER MLflow patches above, so MLflow has finished restarting and alembic has created the spans table.
echo "  Waiting for MLflow to be ready..."
oc wait --for=condition=Available deployment/mlflow -n "$NAMESPACE" --timeout=180s 2>/dev/null || true
echo "  Installing MLflow trace-name trigger..."
POSTGRES_POD=$(oc get pods -n "$NAMESPACE" -l app=postgres-otel -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$POSTGRES_POD" ]; then
  oc exec "$POSTGRES_POD" -n "$NAMESPACE" -- psql -U testuser -d mlflow -c "
    CREATE OR REPLACE FUNCTION set_trace_name_from_root_span()
    RETURNS TRIGGER AS \$\$
    BEGIN
        IF NEW.parent_span_id IS NULL THEN
            INSERT INTO trace_tags (request_id, key, value)
            VALUES (NEW.trace_id, 'mlflow.traceName', NEW.name)
            ON CONFLICT (request_id, key) DO UPDATE SET value = EXCLUDED.value;
        END IF;
        RETURN NEW;
    END;
    \$\$ LANGUAGE plpgsql;
    DO \$\$ BEGIN
        CREATE TRIGGER trg_set_trace_name
            AFTER INSERT ON spans
            FOR EACH ROW
            EXECUTE FUNCTION set_trace_name_from_root_span();
    EXCEPTION WHEN duplicate_object THEN NULL;
    END \$\$;
  " 2>/dev/null && echo "    done" || echo "    skipped (postgres-otel not ready)"
else
  echo "    skipped (postgres-otel not found)"
fi

# ---------------------------------------------------------------------------
# Phase 8: Clean up Keycloak users — keep only admin, create keycloak-admin secret
# ---------------------------------------------------------------------------
echo "[8/9] Cleaning up Keycloak realm users..."
KC_ROUTE=$(oc get route keycloak -n "$KC_NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null)
KC_BOOTSTRAP_USER=$(oc get secret keycloak-initial-admin -n "$KC_NAMESPACE" -o go-template='{{.data.username | base64decode}}' 2>/dev/null)
KC_BOOTSTRAP_PASS=$(oc get secret keycloak-initial-admin -n "$KC_NAMESPACE" -o go-template='{{.data.password | base64decode}}' 2>/dev/null)

if [ -n "$KC_ROUTE" ] && [ -n "$KC_BOOTSTRAP_USER" ]; then
  KC_TOKEN=$(curl -sk -X POST "https://${KC_ROUTE}/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=${KC_BOOTSTRAP_USER}" \
    -d "password=${KC_BOOTSTRAP_PASS}" \
    -d "grant_type=password" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

  if [ -n "$KC_TOKEN" ]; then
    MASTER_API="https://${KC_ROUTE}/admin/realms/master"
    KC_REALM_API="https://${KC_ROUTE}/admin/realms/kagenti"
    ADMIN_PASS="$(openssl rand -hex 16)"

    # --- master realm: create admin user ---
    MASTER_ADMIN_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
      "${MASTER_API}/users?username=admin&exact=true" 2>/dev/null | \
      python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")

    if [ -z "$MASTER_ADMIN_UID" ]; then
      curl -sk -X POST "${MASTER_API}/users" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"admin\",\"enabled\":true,\"credentials\":[{\"type\":\"password\",\"value\":\"${ADMIN_PASS}\",\"temporary\":false}]}" 2>/dev/null
      MASTER_ADMIN_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
        "${MASTER_API}/users?username=admin&exact=true" 2>/dev/null | \
        python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
      echo "  Created admin in master realm."
    else
      curl -sk -X PUT "${MASTER_API}/users/${MASTER_ADMIN_UID}/reset-password" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"type\":\"password\",\"value\":\"${ADMIN_PASS}\",\"temporary\":false}" 2>/dev/null
      echo "  Reset admin password in master realm."
    fi
    if [ -n "$MASTER_ADMIN_UID" ]; then
      MASTER_ADMIN_ROLE=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" "${MASTER_API}/roles/admin" 2>/dev/null)
      if [ -n "$MASTER_ADMIN_ROLE" ] && [ "$MASTER_ADMIN_ROLE" != "null" ]; then
        curl -sk -X POST "${MASTER_API}/users/${MASTER_ADMIN_UID}/role-mappings/realm" \
          -H "Authorization: Bearer ${KC_TOKEN}" \
          -H "Content-Type: application/json" \
          -d "[${MASTER_ADMIN_ROLE}]" 2>/dev/null
      fi
    fi

    # --- kagenti realm: reset admin password (same password) ---
    ADMIN_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
      "${KC_REALM_API}/users?username=admin&exact=true" 2>/dev/null | \
      python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")

    if [ -n "$ADMIN_UID" ]; then
      curl -sk -X PUT "${KC_REALM_API}/users/${ADMIN_UID}/reset-password" \
        -H "Authorization: Bearer ${KC_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"type\":\"password\",\"value\":\"${ADMIN_PASS}\",\"temporary\":false}" 2>/dev/null
      echo "  Reset admin password in kagenti realm."
    fi

    # Delete unnecessary users from kagenti realm
    for DEL_USER in alice bob dev-user ns-admin temp-admin; do
      DEL_UID=$(curl -sk -H "Authorization: Bearer ${KC_TOKEN}" \
        "${KC_REALM_API}/users?username=${DEL_USER}&exact=true" 2>/dev/null | \
        python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id'] if u else '')" 2>/dev/null || echo "")
      if [ -n "$DEL_UID" ]; then
        curl -sk -X DELETE "${KC_REALM_API}/users/${DEL_UID}" \
          -H "Authorization: Bearer ${KC_TOKEN}" 2>/dev/null
        echo "  Deleted user: ${DEL_USER}"
      fi
    done

    # Delete old chart-generated secrets and create keycloak-admin
    oc delete secret kagenti-test-user -n "$KC_NAMESPACE" --ignore-not-found 2>/dev/null
    oc delete secret kagenti-test-users -n "$KC_NAMESPACE" --ignore-not-found 2>/dev/null
    oc delete secret kagenti-admin -n "$KC_NAMESPACE" --ignore-not-found 2>/dev/null
    oc create secret generic keycloak-admin -n "$KC_NAMESPACE" \
      --from-literal=username=admin \
      --from-literal=password="${ADMIN_PASS}" \
      --dry-run=client -o yaml | oc apply -f - 2>/dev/null

    # Sync to kagenti-system so oauth-secret jobs use the same admin
    KC_USER_B64=$(echo -n "admin" | base64)
    KC_PASS_B64=$(echo -n "${ADMIN_PASS}" | base64)
    oc patch secret keycloak-admin-secret -n "$NAMESPACE" --type='json' \
      -p="[{\"op\":\"replace\",\"path\":\"/data/KEYCLOAK_ADMIN_USERNAME\",\"value\":\"${KC_USER_B64}\"},{\"op\":\"replace\",\"path\":\"/data/KEYCLOAK_ADMIN_PASSWORD\",\"value\":\"${KC_PASS_B64}\"}]" \
      2>/dev/null || true
    echo "  Credentials: secret keycloak-admin ($KC_NAMESPACE) + keycloak-admin-secret ($NAMESPACE)."
  else
    echo "  WARNING: Could not obtain Keycloak token, skipping user cleanup."
  fi
fi

# ---------------------------------------------------------------------------
# Phase 9: Verify
# ---------------------------------------------------------------------------
echo "[9/9] Verifying installation..."
echo ""
echo "Pods in $NAMESPACE:"
oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | head -20
echo ""
echo "Pods in $KC_NAMESPACE:"
oc get pods -n "$KC_NAMESPACE" --no-headers 2>/dev/null | head -10
echo ""
echo "Pods in $MCP_NAMESPACE:"
oc get pods -n "$MCP_NAMESPACE" --no-headers 2>/dev/null | head -10
echo ""

echo "=== Installation complete ==="
echo ""
echo "Routes:"
oc get routes -n "$KC_NAMESPACE" --no-headers 2>/dev/null | awk '{printf "  %-15s https://%s\n", $1, $2}'
oc get routes -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{printf "  %-15s https://%s\n", $1, $2}'
