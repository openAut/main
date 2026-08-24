#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="${OPENAUT_ROOT:-$(cd "$HERE/.." && pwd)}"
deploy="$root/deploy/platform-poc1"
pki="$deploy/pki"
field_interface="${OPENAUT_FIELD_INTERFACE:-eth1}"
field_ip="${OPENAUT_FIELD_BIND_IP:-$(ip -4 -o address show dev "$field_interface" scope global | awk 'NR == 1 { split($4, a, "/"); print a[1] }')}"

test -f "$deploy/compose.yaml"
if [ -z "$field_ip" ]; then
  echo "No IPv4 address found on field interface $field_interface." >&2
  exit 1
fi
umask 077
mkdir -p "$deploy/secrets" "$deploy/runtime/certs" \
  "$deploy/runtime/pki/ca" "$deploy/runtime/pki/clients/poc-lab"

for name in postgres_password ingest_db_password agent_ro_db_password; do
  if [ ! -s "$deploy/secrets/$name" ]; then
    openssl rand -hex 32 > "$deploy/secrets/$name"
  fi
done
# The directory remains 0700. Read-only file mode lets non-root container UIDs consume mounted
# secrets without exposing the directory to other host users.
chmod 0444 "$deploy/secrets/"*

if [ ! -s "$deploy/secrets/emqx_cookie" ]; then
  openssl rand -hex 32 > "$deploy/secrets/emqx_cookie"
fi
chmod 0400 "$deploy/secrets/emqx_cookie"
{
  printf 'EMQX_NODE_COOKIE=%s\n' "$(cat "$deploy/secrets/emqx_cookie")"
  printf 'OPENAUT_FIELD_BIND_IP=%s\n' "$field_ip"
} > "$deploy/.env"
chmod 0600 "$deploy/.env"

cat > "$root/config.env" <<EOF
PKI_DIR="$pki"
EMQX_HOST="$field_ip"
EMQX_TLS_PORT="8883"
MQTT_CA_CERT="$pki/ca/ca.crt"
EDGE_SITE="poc-lab"
EDGE_NODE_ID="iot2050-poc-01"
TSDB_HOST="127.0.0.1"
TSDB_PORT="5432"
TSDB_DB="openaut"
TSDB_INGEST_USER="ingest"
TSDB_AGENT_RO_USER="agent_ro"
EOF
chmod 600 "$root/config.env"

chmod +x "$root/skills/mqtt-tls-broker/scripts/"*.sh
chmod +x "$deploy/db/002-roles.sh"

cd "$root"
# gen-certs.sh sources the root config.env written above, including PKI_DIR.
bash skills/mqtt-tls-broker/scripts/gen-certs.sh ca
bash skills/mqtt-tls-broker/scripts/gen-certs.sh broker emqx "$field_ip"
bash skills/mqtt-tls-broker/scripts/gen-certs.sh client poc-lab iot2050-poc-01
bash skills/mqtt-tls-broker/scripts/gen-certs.sh service ingest

install -m 0644 "$pki/ca/ca.crt" "$deploy/runtime/certs/ca.crt"
install -m 0644 "$pki/broker/emqx.crt" "$deploy/runtime/certs/broker.crt"
install -m 0600 "$pki/broker/emqx.key" "$deploy/runtime/certs/broker.key"
install -m 0644 "$pki/ca/ca.crt" "$deploy/runtime/pki/ca/ca.crt"
install -m 0644 "$pki/clients/ingest.crt" "$deploy/runtime/pki/clients/ingest.crt"
install -m 0600 "$pki/clients/ingest.key" "$deploy/runtime/pki/clients/ingest.key"
install -m 0644 "$pki/clients/poc-lab/iot2050-poc-01.crt" \
  "$deploy/runtime/pki/clients/poc-lab/iot2050-poc-01.crt"
install -m 0600 "$pki/clients/poc-lab/iot2050-poc-01.key" \
  "$deploy/runtime/pki/clients/poc-lab/iot2050-poc-01.key"

cd "$deploy"
docker compose config --quiet
echo "POC1 configuration and PKI prepared successfully."
