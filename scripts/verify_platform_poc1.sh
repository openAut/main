#!/usr/bin/env bash
set -euo pipefail

root="$HOME/openaut"
deploy="$root/deploy/platform-poc1"
cd "$root"
set -a
# shellcheck disable=SC1091
. ./config.env
set +a

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

mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$edge_crt" --key "$edge_key" -q 1 \
  -t "openaut/$EDGE_SITE/$EDGE_NODE_ID/ahu/supply_temp" \
  -m "{\"value\":21.5,\"ts\":$ts,\"unit\":\"degC\"}"
mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$edge_crt" --key "$edge_key" -q 1 \
  -t "openaut/$EDGE_SITE/$EDGE_NODE_ID/\$status" \
  -m "{\"value\":true,\"ts\":$ts}"

for _ in $(seq 1 10); do
  telemetry_count="$(docker compose --project-directory "$deploy" exec --no-TTY timescaledb \
    psql -U postgres -d openaut -Atc "SELECT count(*) FROM telemetry.readings WHERE site='$EDGE_SITE' AND node='$EDGE_NODE_ID' AND metric='supply_temp' AND ts=to_timestamp($ts)")"
  status_count="$(docker compose --project-directory "$deploy" exec --no-TTY timescaledb \
    psql -U postgres -d openaut -Atc "SELECT count(*) FROM telemetry.node_status WHERE site='$EDGE_SITE' AND node='$EDGE_NODE_ID' AND ts=to_timestamp($ts)")"
  [ "$telemetry_count" = "1" ] && [ "$status_count" = "1" ] && break
  sleep 1
done
[ "$telemetry_count" = "1" ]
[ "$status_count" = "1" ]

timescale_version="$(docker compose --project-directory "$deploy" exec --no-TTY timescaledb \
  psql -U postgres -d openaut -Atc "SELECT extversion FROM pg_extension WHERE extname='timescaledb'")"
hypertable_count="$(docker compose --project-directory "$deploy" exec --no-TTY timescaledb \
  psql -U postgres -d openaut -Atc "SELECT count(*) FROM timescaledb_information.hypertables")"
[ "$hypertable_count" -ge 2 ]

agent_password="$(cat "$deploy/secrets/agent_ro_db_password")"
[[ "$agent_password" =~ ^[0-9a-f]{64}$ ]]
pgpass="$(mktemp)"
chmod 600 "$pgpass"
printf '127.0.0.1:5432:openaut:agent_ro:%s\n' "$agent_password" > "$pgpass"
unset agent_password
trap 'rm -f "$pgpass"' EXIT
PGPASSFILE="$pgpass" psql -h 127.0.0.1 -U agent_ro -d openaut \
  -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM telemetry.readings" >/dev/null
if PGPASSFILE="$pgpass" psql -h 127.0.0.1 -U agent_ro -d openaut \
  -v ON_ERROR_STOP=1 -c "INSERT INTO telemetry.node_status(ts,site,node,online) VALUES(now(),'denied','denied',true)" \
  >/dev/null 2>&1; then
  echo "FAIL — agent_ro was able to insert telemetry." >&2
  exit 1
fi
if PGPASSFILE="$pgpass" psql -h 127.0.0.1 -U agent_ro -d openaut \
  -v ON_ERROR_STOP=1 -c "UPDATE telemetry.node_status SET online=false WHERE site='$EDGE_SITE'" \
  >/dev/null 2>&1; then
  echo "FAIL — agent_ro was able to update telemetry." >&2
  exit 1
fi

echo "POC1_OK telemetry=$telemetry_count status=$status_count timescaledb=$timescale_version hypertables=$hypertable_count agent_ro_select=allowed agent_ro_write=denied"
