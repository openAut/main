#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${OPENAUT_ROOT:-$(cd "$HERE/.." && pwd)}"
DEPLOY="$ROOT/deploy/platform-poc1"
MIGRATION="$DEPLOY/db/003-edge-event-id.sql"

cd "$DEPLOY"
docker compose exec --no-TTY timescaledb \
  psql --set ON_ERROR_STOP=1 --username postgres --file - < "$MIGRATION"

echo "Platform event_id migration applied."
