#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="${OPENAUT_ROOT:-$(cd "$HERE/.." && pwd)}"
deploy="$root/deploy/platform-poc1"
cd "$root"
set -a
# shellcheck disable=SC1091
. ./config.env
set +a

validate_id() {
  [[ "$1" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]]
}
validate_id "$EDGE_SITE"
validate_id "$EDGE_NODE_ID"

admin_pgpass=""
agent_pgpass=""
counts_file=""
cleanup() {
  for file in "${admin_pgpass:-}" "${agent_pgpass:-}" "${counts_file:-}"; do
    [ -z "$file" ] || rm -f "$file"
  done
}
trap cleanup EXIT

postgres_password="$(cat "$deploy/secrets/postgres_password")"
[[ "$postgres_password" =~ ^[0-9a-f]{64}$ ]]
admin_pgpass="$(mktemp)"
chmod 600 "$admin_pgpass"
printf '127.0.0.1:5432:*:postgres:%s\n' "$postgres_password" > "$admin_pgpass"
unset postgres_password

docker compose --project-directory "$deploy" ps --status running | grep -q timescaledb
docker compose --project-directory "$deploy" ps --status running | grep -q emqx
docker compose --project-directory "$deploy" ps --status running | grep -q ingest

if bash skills/mqtt-tls-broker/scripts/gen-certs.sh service unsupported-service >/dev/null 2>&1; then
  echo "FAIL — certificate helper issued an unknown service identity without an ACL update." >&2
  exit 1
fi

bash skills/mqtt-tls-broker/scripts/verify-tls.sh

edge_crt="$PKI_DIR/clients/$EDGE_SITE/$EDGE_NODE_ID.crt"
edge_key="$PKI_DIR/clients/$EDGE_SITE/$EDGE_NODE_ID.key"
ts="$(date +%s)"
[[ "$ts" =~ ^[0-9]+$ ]]

echo "== Publish synthetic telemetry and status =="
timeout 10 mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$edge_crt" --key "$edge_key" -q 1 \
  -t "openaut/$EDGE_SITE/$EDGE_NODE_ID/ahu/supply_temp" \
  -m "{\"value\":21.5,\"ts\":$ts,\"unit\":\"degC\"}"
timeout 10 mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$edge_crt" --key "$edge_key" -q 1 \
  -t "openaut/$EDGE_SITE/$EDGE_NODE_ID/\$status" \
  -m "{\"value\":true,\"ts\":$ts}"

query_counts() {
  PGCONNECT_TIMEOUT=5 PGPASSFILE="$admin_pgpass" psql -h 127.0.0.1 \
    -v ON_ERROR_STOP=1 -U postgres -d openaut -At \
    --set=edge_site="$EDGE_SITE" --set=edge_node="$EDGE_NODE_ID" --set=event_ts="$ts" \
    --file="$deploy/db/verify-counts.sql" </dev/null
}

echo "== Confirm synthetic rows in TimescaleDB =="
for _ in $(seq 1 10); do
  counts_file="$(mktemp)"
  chmod 600 "$counts_file"
  query_counts > "$counts_file"
  telemetry_count="$(sed -n '1p' "$counts_file")"
  status_count="$(sed -n '2p' "$counts_file")"
  rm -f "$counts_file"
  [ "$telemetry_count" = "1" ] && [ "$status_count" = "1" ] && break
  sleep 1
done
[ "$telemetry_count" = "1" ]
[ "$status_count" = "1" ]

echo "== Confirm TimescaleDB metadata =="
timescale_version="$(PGCONNECT_TIMEOUT=5 PGPASSFILE="$admin_pgpass" psql -h 127.0.0.1 \
  -U postgres -d openaut -Atc "SELECT extversion FROM pg_extension WHERE extname='timescaledb'" </dev/null)"
hypertable_count="$(PGCONNECT_TIMEOUT=5 PGPASSFILE="$admin_pgpass" psql -h 127.0.0.1 \
  -U postgres -d openaut -Atc "SELECT count(*) FROM timescaledb_information.hypertables" </dev/null)"
[ "$hypertable_count" -ge 2 ]

echo "== Confirm agent_ro read-only access =="
agent_password="$(cat "$deploy/secrets/agent_ro_db_password")"
[[ "$agent_password" =~ ^[0-9a-f]{64}$ ]]
agent_pgpass="$(mktemp)"
chmod 600 "$agent_pgpass"
printf '127.0.0.1:5432:openaut:agent_ro:%s\n' "$agent_password" > "$agent_pgpass"
unset agent_password
PGCONNECT_TIMEOUT=5 PGPASSFILE="$agent_pgpass" psql -h 127.0.0.1 -U agent_ro -d openaut \
  -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM telemetry.readings" </dev/null >/dev/null
if PGCONNECT_TIMEOUT=5 PGPASSFILE="$agent_pgpass" psql -h 127.0.0.1 -U agent_ro -d openaut \
  -v ON_ERROR_STOP=1 -c "INSERT INTO telemetry.node_status(ts,site,node,online) VALUES(now(),'denied','denied',true)" \
  </dev/null >/dev/null 2>&1; then
  echo "FAIL — agent_ro was able to insert telemetry." >&2
  exit 1
fi
if printf "UPDATE telemetry.node_status SET online=false WHERE site=:'edge_site';\n" | \
  PGCONNECT_TIMEOUT=5 PGPASSFILE="$agent_pgpass" psql -h 127.0.0.1 -U agent_ro -d openaut \
    -v ON_ERROR_STOP=1 --set=edge_site="$EDGE_SITE" >/dev/null 2>&1; then
  echo "FAIL — agent_ro was able to update telemetry." >&2
  exit 1
fi

echo "POC1_OK telemetry=$telemetry_count status=$status_count timescaledb=$timescale_version hypertables=$hypertable_count agent_ro_select=allowed agent_ro_write=denied"
