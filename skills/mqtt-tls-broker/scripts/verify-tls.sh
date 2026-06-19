#!/usr/bin/env bash
# Verify the EMQX mutual-TLS listener: publish as the edge node's client cert,
# subscribe over TLS, and confirm plaintext :1883 is refused.
# Requires mosquitto-clients locally. Sources ../../../config.env.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$ROOT/config.env"; set +a

PKI="${PKI_DIR:-$ROOT/pki}"
TOPIC="openaut/${EDGE_SITE}/${EDGE_NODE_ID}/selftest/ping"
CLIENT_CRT="$PKI/clients/${EDGE_NODE_ID}.crt"
CLIENT_KEY="$PKI/clients/${EDGE_NODE_ID}.key"

echo "== Subscribe (5s) over TLS to $TOPIC =="
timeout 5 mosquitto_sub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$CLIENT_CRT" --key "$CLIENT_KEY" \
  -t "$TOPIC" -v &
sub=$!
sleep 1

echo "== Publish over TLS as ${EDGE_NODE_ID} =="
mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$CLIENT_CRT" --key "$CLIENT_KEY" \
  -t "$TOPIC" -m "{\"value\":1,\"ts\":$(date +%s),\"unit\":\"ping\"}"
wait $sub 2>/dev/null || true

echo "== Confirm plaintext :1883 is refused (expect failure) =="
if timeout 3 mosquitto_pub -h "$EMQX_HOST" -p 1883 -t "$TOPIC" -m x 2>/dev/null; then
  echo "FAIL — plaintext :1883 accepted a connection; close/firewall it." >&2
  exit 1
else
  echo "OK — plaintext :1883 refused."
fi
