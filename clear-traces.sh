#!/bin/bash
# Clear all tracing data from MLflow experiment
set -uo pipefail

KAGENTI_NS="${KAGENTI_NS:-kagenti-system}"
EXPERIMENT_ID="${EXPERIMENT_ID:-1}"

POSTGRES_POD=$(oc get pods -n "$KAGENTI_NS" -l app=postgres-otel \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POSTGRES_POD" ]; then
  echo "ERROR: postgres-otel pod not found in $KAGENTI_NS"
  exit 1
fi

COUNT=$(oc exec "$POSTGRES_POD" -n "$KAGENTI_NS" -- \
  psql -U testuser -d mlflow -tAc \
  "SELECT count(*) FROM trace_info WHERE experiment_id = $EXPERIMENT_ID;" 2>/dev/null)

echo "Found $COUNT traces in experiment $EXPERIMENT_ID"

if [ "$COUNT" -eq 0 ]; then
  echo "Nothing to delete."
  exit 0
fi

read -p "Delete all $COUNT traces? [y/N] " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

oc exec "$POSTGRES_POD" -n "$KAGENTI_NS" -- \
  psql -U testuser -d mlflow -c \
  "DELETE FROM trace_info WHERE experiment_id = $EXPERIMENT_ID;"

echo "Done."
