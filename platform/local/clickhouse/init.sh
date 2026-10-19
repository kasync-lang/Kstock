#!/bin/bash
# Runs once on an empty volume: create the ohlcv_* tables in $CLICKHOUSE_DB
# (DDL from data/processing/ohlcv-aggregator/aggregate_db).
set -euo pipefail

for f in /ddl/aggregate_db/*.sql; do
  echo "$CLICKHOUSE_DB <- $(basename "$f")"
  clickhouse client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" \
    --database "$CLICKHOUSE_DB" --multiquery < "$f"
done
