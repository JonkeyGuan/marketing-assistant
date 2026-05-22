#!/bin/bash
# Stop MongoDB locally

podman stop mongodb 2>/dev/null
podman rm mongodb 2>/dev/null
echo "MongoDB stopped"
