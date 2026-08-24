#!/usr/bin/env bash
set -euo pipefail

deploy="$HOME/openaut/deploy/platform-poc1"
cd "$deploy"

ingest_password="$(cat secrets/ingest_db_password)"
agent_ro_password="$(cat secrets/agent_ro_db_password)"

docker compose exec --no-TTY timescaledb psql --username postgres --dbname openaut \
  --set=ingest_password="$ingest_password" \
  --set=agent_ro_password="$agent_ro_password" <<'SQL'
ALTER ROLE ingest PASSWORD :'ingest_password';
ALTER ROLE agent_ro PASSWORD :'agent_ro_password';
SQL

echo "Database role passwords applied."
