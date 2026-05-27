#!/bin/bash
set -e

TAG="${1:-2.0}"
REGISTRY="quay.io/jonkey/marketing-assistant"

SERVICES=(
  campaign-api
  campaign-director
  campaign-landing
  config-service
  creative-producer
  customer-analyst
  delivery-manager
  event-hub
  frontend
  imagegen-mcp
  mongodb-mcp
  policy-guardian
)

FAILED=()

for svc in "${SERVICES[@]}"; do
  echo "============================================"
  echo "Building ${svc}:${TAG}"
  echo "============================================"
  if (cd "$svc" && podman build --platform linux/amd64 -f Containerfile -t "${REGISTRY}/${svc}:${TAG}" .); then
    echo "Pushing ${REGISTRY}/${svc}:${TAG}"
    podman push "${REGISTRY}/${svc}:${TAG}"
    echo "Done: ${svc}:${TAG}"
  else
    echo "FAILED: ${svc}"
    FAILED+=("$svc")
  fi
  echo
done

echo "============================================"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "All ${#SERVICES[@]} services built and pushed as :${TAG}"
else
  echo "Failed (${#FAILED[@]}): ${FAILED[*]}"
  exit 1
fi
