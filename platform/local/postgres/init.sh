#!/bin/bash
# Runs once on an empty volume (docker-entrypoint-initdb.d).
#   interactdb : core-api business tables (DDL from backend/core-api/docs/public)
#   newsdb     : news-processing tables
#   airflow    : Airflow metadata
set -euo pipefail

psql_as() { psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$1" "${@:2}"; }

psql_as postgres -c "CREATE DATABASE newsdb;"
psql_as postgres -c "CREATE DATABASE airflow;"

# FK order matters
for t in user_table company_profile alert triggeralert assets cash note favorite_symbols transaction; do
  echo "interactdb <- $t.sql"
  psql_as "$POSTGRES_DB" -f "/ddl/interactdb/$t.sql"
done

echo "newsdb <- schema.sql"
psql_as newsdb -f /ddl/newsdb/schema.sql
