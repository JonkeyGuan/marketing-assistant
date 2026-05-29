#!/bin/bash
# Deploy LLM models to OpenShift via KServe + HuggingFace auto-download
#
# Each model pod downloads its weights from HuggingFace on first start.
# PVCs cache the downloaded models so subsequent restarts skip the download.
set -uo pipefail

NAMESPACE="${NAMESPACE:-models}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS=(qwen3-32b-fp8-dynamic flux2-klein-4b qwen3-coder-30b)

echo "=== Model Deployment ==="
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
# Phase 1: Create ServiceAccount + token + RBAC for each model
# ---------------------------------------------------------------------------
echo "[1/2] Creating auth resources..."

for MODEL in "${MODELS[@]}"; do
  SA_NAME="${MODEL}-sa"

  # ServiceAccount
  oc create serviceaccount "$SA_NAME" -n "$NAMESPACE" --dry-run=client -o yaml | oc apply -f - -n "$NAMESPACE" 2>/dev/null

  # Token Secret
  cat <<EOF | oc apply -f - -n "$NAMESPACE" 2>/dev/null
apiVersion: v1
kind: Secret
metadata:
  name: ${SA_NAME}
  namespace: ${NAMESPACE}
  annotations:
    kubernetes.io/service-account.name: ${SA_NAME}
  labels:
    opendatahub.io/dashboard: 'true'
type: kubernetes.io/service-account-token
EOF

  # Role
  cat <<EOF | oc apply -f - -n "$NAMESPACE" 2>/dev/null
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ${MODEL}-view
  namespace: ${NAMESPACE}
  labels:
    opendatahub.io/dashboard: 'true'
rules:
  - verbs: ["get"]
    apiGroups: ["serving.kserve.io"]
    resources: ["inferenceservices"]
    resourceNames: ["${MODEL}"]
EOF

  # RoleBinding
  cat <<EOF | oc apply -f - -n "$NAMESPACE" 2>/dev/null
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${SA_NAME}-${MODEL}-view
  namespace: ${NAMESPACE}
  labels:
    opendatahub.io/dashboard: 'true'
subjects:
  - kind: ServiceAccount
    name: ${SA_NAME}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: ${MODEL}-view
EOF

  echo "  $MODEL: SA + token + RBAC"
done

# ---------------------------------------------------------------------------
# Phase 2: Deploy models
# ---------------------------------------------------------------------------
echo "[2/2] Deploying models..."

for f in "$SCRIPT_DIR"/*.yaml; do
  echo "  $(basename "$f")"
  oc apply -f "$f" -n "$NAMESPACE" 2>/dev/null || true
done

echo ""
echo "=== Model deployment complete ==="
echo ""
echo "Tokens:"
for MODEL in "${MODELS[@]}"; do
  TOKEN=$(oc get secret "${MODEL}-sa" -n "$NAMESPACE" -o go-template='{{.data.token | base64decode}}' 2>/dev/null | head -c 40)
  echo "  $MODEL: ${TOKEN}..."
done
echo ""
echo "Usage: NAMESPACE=<ns> $0"
