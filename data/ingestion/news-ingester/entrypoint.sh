#!/usr/bin/env bash
set -euo pipefail
echo "Checking for required environment variables..."
# ====== Required environment variables ======
REQUIRED_ENVS=(
  "SECRET_KEY_HUB"
  # Default sink in `main.py` is S3, so require bucket.
  "S3_BUCKET"
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
exec "$@"
