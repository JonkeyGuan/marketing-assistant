#!/bin/bash
set -e

IMAGE="quay.io/jonkey/orchestrator"
TAG="${1:-latest}"

podman build -f Containerfile -t ${IMAGE}:${TAG} .
podman push ${IMAGE}:${TAG}

echo "Pushed ${IMAGE}:${TAG}"
