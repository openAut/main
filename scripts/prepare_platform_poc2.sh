#!/usr/bin/env bash
set -euo pipefail

poc1="$HOME/openaut/deploy/platform-poc1"
poc2="$HOME/openaut/deploy/platform-poc2"
mkdir -p "$poc2/secrets"
chmod 700 "$poc2/secrets"

if [ ! -s "$poc2/secrets/forgejo_db_password" ]; then
  openssl rand -hex 32 > "$poc2/secrets/forgejo_db_password"
fi
chmod 0400 "$poc2/secrets/forgejo_db_password"
forgejo_password="$(cat "$poc2/secrets/forgejo_db_password")"
printf 'FORGEJO_DB_PASSWORD=%s\n' "$forgejo_password" > "$poc2/.env"
chmod 0600 "$poc2/.env"

docker compose --project-directory "$poc1" exec --no-TTY timescaledb \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  < "$poc2/db/001-system.sql"

docker compose --project-directory "$poc1" exec --no-TTY timescaledb \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres --set=forgejo_password="$forgejo_password" <<'SQL'
SELECT format('CREATE ROLE forgejo LOGIN PASSWORD %L', :'forgejo_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'forgejo')\gexec
ALTER ROLE forgejo PASSWORD :'forgejo_password';
SELECT 'CREATE DATABASE forgejo OWNER forgejo'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forgejo')\gexec
SQL

docker compose --project-directory "$poc2" config --quiet
echo "POC2 Forgejo database and configuration prepared."
