#!/usr/bin/env bash
set -euo pipefail

deploy="$HOME/openaut/deploy/platform-poc1"
cd "$deploy"

ingest_password="$(cat secrets/ingest_db_password)"
agent_ro_password="$(cat secrets/agent_ro_db_password)"
[[ "$ingest_password" =~ ^[0-9a-f]{64}$ ]]
[[ "$agent_ro_password" =~ ^[0-9a-f]{64}$ ]]

{
  printf "\\set ingest_password '%s'\n" "$ingest_password"
  printf "\\set agent_ro_password '%s'\n" "$agent_ro_password"
  cat <<'SQL'
ALTER ROLE ingest PASSWORD :'ingest_password';
ALTER ROLE agent_ro PASSWORD :'agent_ro_password';
SQL
} | docker compose exec --no-TTY timescaledb psql --username postgres --dbname openaut
unset ingest_password agent_ro_password

echo "Database role passwords applied."
