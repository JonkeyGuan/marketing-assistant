#!/bin/bash
# Start MongoDB locally via podman

podman run -d --name mongodb --replace \
    -p 27017:27017 \
    -v mongodb_data:/data/db \
    -e MONGO_INITDB_DATABASE=casino_crm \
    quay.io/mongodb/mongodb-community-server:7.0-ubi9

echo "MongoDB running on localhost:27017"
