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

INSERT = (
    "INSERT INTO telemetry.readings (ts, site, node, system, metric, value, bool_val, unit) "
    "VALUES (to_timestamp(%(ts)s), %(site)s, %(node)s, %(system)s, %(metric)s, "
    "%(value)s, %(bool_val)s, %(unit)s)"
)
STATUS_INSERT = (
    "INSERT INTO telemetry.node_status (ts, site, node, online) "
    "VALUES (to_timestamp(%(ts)s), %(site)s, %(node)s, %(online)s)"
)


def parse_topic(topic: str):
    # openaut/<site>/<node>/<system>/<metric>
    parts = topic.split("/")
    if len(parts) != 5 or parts[0] != "openaut":
        return None
    _, site, node, system, metric = parts
    return site, node, system, metric


def parse_status_topic(topic: str):
    # openaut/<site>/<node>/$status
    parts = topic.split("/")
    if len(parts) != 4 or parts[0] != "openaut" or parts[3] != "$status":
        return None
    _, site, node, _status = parts
    return site, node


def telemetry_row(topic: str, payload_bytes: bytes):
    parsed = parse_topic(topic)
    if not parsed:
        return None
    site, node, system, metric = parsed
    try:
        payload = json.loads(payload_bytes)
    except (json.JSONDecodeError, ValueError):
        return None
    val = payload.get("value")
    row = {
        "ts": payload.get("ts"),
        "site": site,
        "node": node,
        "system": system,
        "metric": metric,
        "value": val if isinstance(val, (int, float)) and not isinstance(val, bool) else None,
        "bool_val": val if isinstance(val, bool) else None,
        "unit": payload.get("unit"),
    }
    if row["ts"] is None:
        return None
    return row


def status_row(topic: str, payload_bytes: bytes):
    parsed = parse_status_topic(topic)
    if not parsed:
        return None
    site, node = parsed
    try:
        payload = json.loads(payload_bytes)
    except (json.JSONDecodeError, ValueError):
        return None
    val = payload.get("value")
    if not isinstance(val, bool) or payload.get("ts") is None:
        return None
    return {"ts": payload["ts"], "site": site, "node": node, "online": val}


def main():
    try:
        import paho.mqtt.client as mqtt
        import psycopg
    except ImportError:
        sys.exit("pip install paho-mqtt psycopg[binary]")

    emqx_host = os.environ["EMQX_HOST"]
    emqx_tls_port = int(os.environ.get("EMQX_TLS_PORT", "8883"))
    ca = os.environ["MQTT_CA_CERT"]
    pki = os.environ.get("PKI_DIR", "./pki")
    cert = f"{pki}/clients/ingest.crt"
    key = f"{pki}/clients/ingest.key"
    dsn = (
        f"host={os.environ['TSDB_HOST']} port={os.environ.get('TSDB_PORT','5432')} "
        f"dbname={os.environ['TSDB_DB']} user={os.environ.get('TSDB_INGEST_USER','ingest')}"
    )  # password via PGPASSWORD / .pgpass

    conn = psycopg.connect(dsn, autocommit=True)

    def on_connect(client, _u, _f, rc, *_):
        print(f"connected rc={rc}; subscribing openaut/#")
        client.subscribe("openaut/#", qos=1)

    def on_message(_c, _u, msg):
        status = status_row(msg.topic, msg.payload)
        if status:
            try:
                conn.execute(STATUS_INSERT, status)
            except Exception as exc:  # noqa: BLE001
                print(f"status insert failed for {msg.topic}: {exc}", file=sys.stderr)
            return
        row = telemetry_row(msg.topic, msg.payload)
        if not row:
            return
        try:
            conn.execute(INSERT, row)
        except Exception as exc:  # noqa: BLE001
            print(f"insert failed for {msg.topic}: {exc}", file=sys.stderr)

    client = mqtt.Client(client_id="ingest")
    client.tls_set(ca_certs=ca, certfile=cert, keyfile=key, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(emqx_host, emqx_tls_port, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
