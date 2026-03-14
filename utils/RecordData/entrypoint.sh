#!/bin/bash
set -e
require_vars=(
"KAFKA_BOOTSTRAP_SERVERS"
"KAFKA_GROUP_ID"
"KAFKA_TOPIC"
)
missing=0
for var in "${require_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "ERROR: Environment variable $var is not set"
    missing=1
  fi
done
if [ "$missing" -eq 1 ]; then
  echo "Startup aborted due to missing environment variables"
  exit 1
fi
echo "All required environment variables are set"

exec "$@"