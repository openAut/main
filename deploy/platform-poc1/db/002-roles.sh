#!/usr/bin/env bash
set -euo pipefail

ingest_password="$(cat /run/secrets/ingest_db_password)"
agent_ro_password="$(cat /run/secrets/agent_ro_db_password)"
[[ "$ingest_password" =~ ^[0-9a-f]{64}$ ]]
[[ "$agent_ro_password" =~ ^[0-9a-f]{64}$ ]]

{
  printf "\\set ingest_password '%s'\n" "$ingest_password"
  printf "\\set agent_ro_password '%s'\n" "$agent_ro_password"
  cat <<'SQL'
ALTER ROLE ingest PASSWORD :'ingest_password';
ALTER ROLE agent_ro PASSWORD :'agent_ro_password';
SQL
} | psql --username "$POSTGRES_USER" --dbname openaut
unset ingest_password agent_ro_password
