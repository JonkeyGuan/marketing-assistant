#!/bin/bash
set -e

IMAGE="quay.io/jonkey/marketing-assistant/config-service"
TAG="${1:-latest}"

podman build --platform linux/amd64 -f Containerfile -t ${IMAGE}:${TAG} .
podman push ${IMAGE}:${TAG}

echo "Pushed ${IMAGE}:${TAG}"
