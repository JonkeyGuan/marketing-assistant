#!/usr/bin/env bash
# Fill <TODO> placeholders in k8s.yaml templates to produce .k8s.yaml files.
#
# Reads model tokens from the models namespace and cluster domain from
# OpenShift ingress config, then substitutes into each service's k8s.yaml.
set -uo pipefail

NAMESPACE="${NAMESPACE:-marketing}"
MODEL_NS="${MODEL_NS:-models}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Fill Environment Config ==="
echo "App namespace:   $NAMESPACE"
echo "Model namespace: $MODEL_NS"
echo ""

if ! oc whoami &>/dev/null; then
  echo "ERROR: Not logged in to OpenShift. Run 'oc login' first."
  exit 1
fi

# ---------------------------------------------------------------------------
# Gather values
# ---------------------------------------------------------------------------
echo "Gathering cluster info..."

CLUSTER_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>/dev/null)
if [ -z "$CLUSTER_DOMAIN" ]; then
  echo "ERROR: Could not detect cluster domain."
  exit 1
fi
echo "  CLUSTER_DOMAIN: $CLUSTER_DOMAIN"

echo "Gathering model tokens..."

get_token() {
  oc get secret "${1}-sa" -n "$MODEL_NS" \
    -o go-template='{{.data.token | base64decode}}' 2>/dev/null
}

TOKEN_QWEN3_32B=$(get_token qwen3-32b-fp8-dynamic)
TOKEN_FLUX2=$(get_token flux2-klein-4b)
TOKEN_QWEN3_CODER=$(get_token qwen3-coder-30b)

for name_token in "qwen3-32b-fp8-dynamic:$TOKEN_QWEN3_32B" "flux2-klein-4b:$TOKEN_FLUX2" "qwen3-coder-30b:$TOKEN_QWEN3_CODER"; do
  name="${name_token%%:*}"
  token="${name_token#*:}"
  if [ -z "$token" ]; then
    echo "  WARNING: Token not found for $name"
  else
    echo "  $name: $(echo "$token" | head -c 30)..."
  fi
done

# ---------------------------------------------------------------------------
# Resolve token for a service
# ---------------------------------------------------------------------------
token_for_service() {
  case "$1" in
    creative-producer)  echo "$TOKEN_QWEN3_CODER" ;;
    customer-analyst)   echo "$TOKEN_QWEN3_32B" ;;
    policy-guardian)    echo "$TOKEN_QWEN3_32B" ;;
    delivery-manager)   echo "$TOKEN_QWEN3_32B" ;;
    imagegen-mcp)       echo "$TOKEN_FLUX2" ;;
    *)                  echo "" ;;
  esac
}

# ---------------------------------------------------------------------------
# Generate .k8s.yaml from k8s.yaml for each service
# ---------------------------------------------------------------------------
echo ""
echo "Generating .k8s.yaml files..."

for svc_dir in "$SCRIPT_DIR"/*/; do
  svc=$(basename "$svc_dir")
  src="$svc_dir/k8s.yaml"
  dst="$svc_dir/.k8s.yaml"

  [ ! -f "$src" ] && continue

  if ! grep -q '<TODO>' "$src" 2>/dev/null; then
    cp "$src" "$dst"
    echo "  $svc: copied (no TODOs)"
    continue
  fi

  TOKEN=$(token_for_service "$svc")

  sed \
    -e "s|CLUSTER_DOMAIN: \"<TODO>\"|CLUSTER_DOMAIN: \"$CLUSTER_DOMAIN\"|g" \
    -e "s|namespace: \"<TODO>\"|namespace: \"$NAMESPACE\"|g" \
    -e "s|MODEL_API_KEY: \"<TODO>\"|MODEL_API_KEY: \"$TOKEN\"|g" \
    "$src" > "$dst"

  echo "  $svc: generated"
done

echo ""
echo "=== Done ==="
echo "Generated .k8s.yaml files are ready for deployment with deploy.sh"
