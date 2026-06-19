#!/usr/bin/env python3
"""openAut MQTT -> TimescaleDB ingest consumer (reference).

Subscribes to openaut/# on the EMQX broker over mutual TLS (as the 'ingest' client cert),
parses openaut/<site>/<node>/<system>/<metric> topics, and inserts into telemetry.readings.

Config from environment (source ../../config.env first):
  EMQX_HOST, EMQX_TLS_PORT, MQTT_CA_CERT
  PKI_DIR            -> client cert/key at $PKI_DIR/clients/ingest.{crt,key}
  TSDB_HOST, TSDB_PORT, TSDB_DB, TSDB_INGEST_USER, PGPASSWORD (out-of-band)

Requires: paho-mqtt, psycopg. Run as a systemd service on the AI-tier host.
Not production-hardened (no batching/backpressure) — see notes in SKILL.md.
"""
import json
import os
import ssl
import sys

try:
    import paho.mqtt.client as mqtt
    import psycopg
except ImportError:
    sys.exit("pip install paho-mqtt psycopg[binary]")

EMQX_HOST = os.environ["EMQX_HOST"]
EMQX_TLS_PORT = int(os.environ.get("EMQX_TLS_PORT", "8883"))
CA = os.environ["MQTT_CA_CERT"]
PKI = os.environ.get("PKI_DIR", "./pki")
CERT = f"{PKI}/clients/ingest.crt"
KEY = f"{PKI}/clients/ingest.key"

DSN = (
    f"host={os.environ['TSDB_HOST']} port={os.environ.get('TSDB_PORT','5432')} "
    f"dbname={os.environ['TSDB_DB']} user={os.environ.get('TSDB_INGEST_USER','ingest')}"
)  # password via PGPASSWORD / .pgpass

INSERT = (
    "INSERT INTO telemetry.readings (ts, site, node, system, metric, value, bool_val, unit) "
    "VALUES (to_timestamp(%(ts)s), %(site)s, %(node)s, %(system)s, %(metric)s, "
    "%(value)s, %(bool_val)s, %(unit)s)"
)


def parse_topic(topic: str):
    # openaut/<site>/<node>/<system>/<metric>
    parts = topic.split("/")
    if len(parts) != 5 or parts[0] != "openaut":
        return None
    _, site, node, system, metric = parts
    return site, node, system, metric


def main():
    conn = psycopg.connect(DSN, autocommit=True)

    def on_connect(client, _u, _f, rc, *_):
        print(f"connected rc={rc}; subscribing openaut/#")
        client.subscribe("openaut/#", qos=1)

    def on_message(_c, _u, msg):
        parsed = parse_topic(msg.topic)
        if not parsed:
            return
        site, node, system, metric = parsed
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, ValueError):
            return
        val = payload.get("value")
        row = {
            "ts": payload.get("ts"),
            "site": site, "node": node, "system": system, "metric": metric,
            "value": val if isinstance(val, (int, float)) and not isinstance(val, bool) else None,
            "bool_val": val if isinstance(val, bool) else None,
            "unit": payload.get("unit"),
        }
        if row["ts"] is None:
            return
        try:
            conn.execute(INSERT, row)
        except Exception as exc:  # noqa: BLE001
            print(f"insert failed for {msg.topic}: {exc}", file=sys.stderr)

    client = mqtt.Client(client_id="ingest")
    client.tls_set(ca_certs=CA, certfile=CERT, keyfile=KEY, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(EMQX_HOST, EMQX_TLS_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
