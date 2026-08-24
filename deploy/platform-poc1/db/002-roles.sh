#!/usr/bin/env bash
set -euo pipefail

ingest_password="$(cat /run/secrets/ingest_db_password)"
agent_ro_password="$(cat /run/secrets/agent_ro_db_password)"

psql --username "$POSTGRES_USER" --dbname openaut \
  --set=ingest_password="$ingest_password" \
  --set=agent_ro_password="$agent_ro_password" <<'SQL'
ALTER ROLE ingest PASSWORD :'ingest_password';
ALTER ROLE agent_ro PASSWORD :'agent_ro_password';
SQL
