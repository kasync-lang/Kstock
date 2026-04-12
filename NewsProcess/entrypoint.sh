#!/usr/bin/env bash
set -euo pipefail
echi "Checking for required environment variables..."
# ====== Required environment variables ======
REQUIRED_ENVS=(
  "SECRET_KEY_HUB"
  "KAFKA_BOOTSTRAP_SERVERS"
  "KAFKA_TOPIC_NEWS_RAW"
 )
MISSING_ENVS=false
for var in "${REQUIRED_ENVS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Error: Environment variable '$var' is not set."
    MISSING_ENVS=true
  fi
done
if [ "$MISSING_ENVS" = true ]; then
  echo "One or more required environment variables are missing. Exiting."
  exit 1
fi
echo "All required environment variables are set."
# ====== Start the application ======
echo "Starting the application with $WORKER_COUNT workers..."
