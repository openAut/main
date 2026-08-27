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
import re
import ssl
import sys
import time

INSERT = (
    "INSERT INTO telemetry.readings (ts, site, node, system, metric, event_id, value, bool_val, unit) "
    "VALUES (to_timestamp(%(ts)s), %(site)s, %(node)s, %(system)s, %(metric)s, %(event_id)s, "
    "%(value)s, %(bool_val)s, %(unit)s) ON CONFLICT (ts, node, event_id) DO NOTHING"
)
STATUS_INSERT = (
    "INSERT INTO telemetry.node_status (ts, site, node, online) "
    "VALUES (to_timestamp(%(ts)s), %(site)s, %(node)s, %(online)s)"
)
EVENT_ID = re.compile(r"[0-9a-f]{32}", flags=re.ASCII)


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
    event_id = payload.get("event_id")
    if event_id is not None and (not isinstance(event_id, str) or EVENT_ID.fullmatch(event_id) is None):
        return None
    row = {
        "ts": payload.get("ts"),
        "site": site,
        "node": node,
        "system": system,
        "metric": metric,
        "event_id": event_id,
        "value": val if isinstance(val, (int, float)) and not isinstance(val, bool) else None,
        "bool_val": val if isinstance(val, bool) else None,
        "unit": payload.get("unit"),
    }
    if row["ts"] is None:
        return None
    return row


def status_row(topic: str, payload_bytes: bytes, received_at=None):
    parsed = parse_status_topic(topic)
    if not parsed:
        return None
    site, node = parsed
    try:
        payload = json.loads(payload_bytes)
    except (json.JSONDecodeError, ValueError):
        return None
    val = payload.get("value")
    if not isinstance(val, bool):
        return None
    timestamp = payload.get("ts")
    # A retained MQTT Last-Will is a current-state observation, not an exact disconnect event.
    # Ingest timestamps when it observes that state; online status remains source-timestamped.
    if timestamp is None and val is False:
        timestamp = received_at
    if timestamp is None:
        return None
    return {"ts": timestamp, "site": site, "node": node, "online": val}


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
    password_file = os.environ.get("PGPASSWORD_FILE")
    if password_file:
        with open(password_file, encoding="utf-8") as handle:
            os.environ["PGPASSWORD"] = handle.read().strip()
    dsn = (
        f"host={os.environ['TSDB_HOST']} port={os.environ.get('TSDB_PORT','5432')} "
        f"dbname={os.environ['TSDB_DB']} user={os.environ.get('TSDB_INGEST_USER','ingest')}"
    )  # password via PGPASSWORD / .pgpass

    conn = None

    def db_execute(statement, row):
        nonlocal conn
        for attempt in range(2):
            try:
                if conn is None or conn.closed:
                    conn = psycopg.connect(dsn, autocommit=True)
                conn.execute(statement, row)
                return
            except psycopg.OperationalError:
                if conn is not None:
                    conn.close()
                conn = None
                if attempt:
                    raise
                time.sleep(1)

    def on_connect(client, _u, _f, rc, *_):
        print(f"connected rc={rc}; subscribing openaut/#")
        client.subscribe("openaut/#", qos=1)

    def on_message(_c, _u, msg):
        status = status_row(msg.topic, msg.payload, received_at=int(time.time()))
        if status:
            try:
                db_execute(STATUS_INSERT, status)
            except Exception as exc:  # noqa: BLE001
                print(f"status insert failed for {msg.topic}: {exc}", file=sys.stderr)
            return
        row = telemetry_row(msg.topic, msg.payload)
        if not row:
            return
        try:
            db_execute(INSERT, row)
        except Exception as exc:  # noqa: BLE001
            print(f"insert failed for {msg.topic}: {exc}", file=sys.stderr)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ingest")
    client.tls_set(ca_certs=ca, certfile=cert, keyfile=key, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(emqx_host, emqx_tls_port, keepalive=60)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
