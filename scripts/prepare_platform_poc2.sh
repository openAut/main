#!/usr/bin/env bash
set -euo pipefail

poc1="$HOME/openaut/deploy/platform-poc1"
poc2="$HOME/openaut/deploy/platform-poc2"
mkdir -p "$poc2/secrets"
chmod 700 "$poc2/secrets"

if [ -e "$poc2/secrets/forgejo_db_password" ]; then
  chmod u+rw "$poc2/secrets/forgejo_db_password"
fi
if [ ! -s "$poc2/secrets/forgejo_db_password" ]; then
  openssl rand -hex 32 | tr -d '\r\n' > "$poc2/secrets/forgejo_db_password"
fi
forgejo_password="$(tr -d '\r\n' < "$poc2/secrets/forgejo_db_password")"
[[ "$forgejo_password" =~ ^[0-9a-f]{64}$ ]]
printf '%s' "$forgejo_password" > "$poc2/secrets/forgejo_db_password"
chmod 0400 "$poc2/secrets/forgejo_db_password"

# Remove files from the superseded full-app.ini migration approach. Forgejo's persistent app.ini
# and its existing encryption/JWT keys remain in the forgejo_data volume and are never replaced.
rm -f "$poc2/.env" "$poc2/secrets/forgejo-app.ini" \
  "$poc2/secrets/forgejo_secret_key" "$poc2/secrets/forgejo_internal_token" \
  "$poc2/secrets/forgejo_jwt_secret" "$poc2/secrets/.forgejo-secrets-initialized"

docker compose --project-directory "$poc1" exec --no-TTY timescaledb \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  < "$poc2/db/001-system.sql"

{
  printf "\\set forgejo_password '%s'\n" "$forgejo_password"
  cat <<'SQL'
SELECT format('CREATE ROLE forgejo LOGIN PASSWORD %L', :'forgejo_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'forgejo')\gexec
ALTER ROLE forgejo PASSWORD :'forgejo_password';
SELECT 'CREATE DATABASE forgejo OWNER forgejo'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forgejo')\gexec
SQL
} | docker compose --project-directory "$poc1" exec --no-TTY timescaledb \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres

docker compose --project-directory "$poc2" config --quiet
unset forgejo_password
echo "POC2 Forgejo database and file-based password configuration prepared."
