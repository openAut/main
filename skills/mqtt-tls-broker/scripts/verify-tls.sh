#!/usr/bin/env bash
# Verify the EMQX mutual-TLS listener: subscribe as the ingest service, publish as the edge node,
# and confirm plaintext :1883 is refused.
# Requires mosquitto-clients locally. Sources ../../../config.env.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$ROOT/config.env"; set +a

PKI="${PKI_DIR:-$ROOT/pki}"
TOPIC="openaut/${EDGE_SITE}/${EDGE_NODE_ID}/selftest/ping"
# gen-certs.sh client "$EDGE_SITE" "$EDGE_NODE_ID" lays cert files out one directory per site,
# one file per node -- not a concatenated "<site>-<node>" name, which isn't collision-free
# since both segments may themselves contain '-' (CN inside is the combined "<site>/<node>",
# see acl.conf and ADR 0004 decision 1).
CLIENT_CRT="$PKI/clients/${EDGE_SITE}/${EDGE_NODE_ID}.crt"
CLIENT_KEY="$PKI/clients/${EDGE_SITE}/${EDGE_NODE_ID}.key"
INGEST_CRT="$PKI/clients/ingest.crt"
INGEST_KEY="$PKI/clients/ingest.key"

echo "== Subscribe (5s) over TLS to $TOPIC =="
out="$(mktemp)"
trap 'rm -f "$out"' EXIT
timeout 8 mosquitto_sub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$INGEST_CRT" --key "$INGEST_KEY" \
  -t "$TOPIC" -v -C 1 > "$out" &
sub=$!
sleep 1

echo "== Publish over TLS as ${EDGE_NODE_ID} =="
mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$CLIENT_CRT" --key "$CLIENT_KEY" \
  -q 1 -t "$TOPIC" -m "{\"value\":1,\"ts\":$(date +%s),\"unit\":\"ping\"}"
if ! wait "$sub"; then
  echo "FAIL — ingest subscriber did not receive the edge publication." >&2
  exit 1
fi
grep -F "$TOPIC" "$out" >/dev/null

echo "== Confirm edge certificate cannot publish outside its own scope =="
denied_topic="openaut/other-site/other-node/selftest/denied"
timeout 4 mosquitto_sub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$INGEST_CRT" --key "$INGEST_KEY" \
  -t "$denied_topic" -C 1 >/dev/null 2>&1 &
denied_sub=$!
sleep 1
mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" -V mqttv5 \
  --cafile "$MQTT_CA_CERT" --cert "$CLIENT_CRT" --key "$CLIENT_KEY" \
  -q 1 -t "$denied_topic" -m x
if wait "$denied_sub"; then
  echo "FAIL — ingest received a wrong-scope edge publication." >&2
  exit 1
else
  echo "OK — wrong-scope publication was not delivered."
fi

echo "== Confirm ingest certificate cannot publish telemetry =="
ingest_denied_topic="openaut/ingest/selftest/denied"
timeout 4 mosquitto_sub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$INGEST_CRT" --key "$INGEST_KEY" \
  -t "$ingest_denied_topic" -C 1 >/dev/null 2>&1 &
ingest_denied_sub=$!
sleep 1
mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" -V mqttv5 \
  --cafile "$MQTT_CA_CERT" --cert "$INGEST_CRT" --key "$INGEST_KEY" \
  -q 1 -t "$ingest_denied_topic" -m x
if wait "$ingest_denied_sub"; then
  echo "FAIL — ingest certificate published telemetry." >&2
  exit 1
else
  echo "OK — ingest publication was not delivered."
fi

echo "== Confirm a client without a certificate is refused =="
if timeout 5 mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" -V mqttv5 \
  --cafile "$MQTT_CA_CERT" -q 1 -t "$TOPIC" -m x 2>/dev/null; then
  echo "FAIL — listener accepted a client without a certificate." >&2
  exit 1
else
  echo "OK — client without certificate refused."
fi

echo "== Confirm a certificate from an untrusted CA is refused =="
rogue_dir="$(mktemp -d)"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -sha256 \
  -subj "/CN=rogue" \
  -keyout "$rogue_dir/rogue.key" -out "$rogue_dir/rogue.crt" >/dev/null 2>&1
if timeout 5 mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" -V mqttv5 \
  --cafile "$MQTT_CA_CERT" --cert "$rogue_dir/rogue.crt" --key "$rogue_dir/rogue.key" \
  -q 1 -t "$TOPIC" -m x 2>/dev/null; then
  rm -rf "$rogue_dir"
  echo "FAIL — listener accepted a certificate from an untrusted CA." >&2
  exit 1
else
  rm -rf "$rogue_dir"
  echo "OK — untrusted certificate refused."
fi

echo "== Confirm plaintext :1883 is refused (expect failure) =="
if timeout 3 mosquitto_pub -h "$EMQX_HOST" -p 1883 -t "$TOPIC" -m x 2>/dev/null; then
  echo "FAIL — plaintext :1883 accepted a connection; close/firewall it." >&2
  exit 1
else
  echo "OK — plaintext :1883 refused."
fi
