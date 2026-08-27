#!/usr/bin/env python3
"""Read-only openAut IOT2050 telemetry publisher reference.

The MQTT/TLS and durable spool contract is implemented here. Field reads remain a stub until one
approved protocol integration wires ``read_point()`` to reviewed hardware and a point map.
"""
import json
import os
import queue
import re
import sqlite3
import ssl
import sys
import threading
import time
import uuid

MQTT_ERR_SUCCESS = 0
CFG = os.environ.get("OPENAUT_POINTS", "/etc/openaut/current/points.json")
CERT_DIR = os.environ.get("OPENAUT_CERT_DIR", "/etc/openaut/current/certs")
BROKER_HOST = os.environ.get("EMQX_HOST")
BROKER_PORT = int(os.environ.get("EMQX_TLS_PORT", "8883"))
SPOOL = os.environ.get("OPENAUT_SPOOL", "/var/lib/openaut/spool.sqlite")
SPOOL_MAX_ROWS = int(os.environ.get("OPENAUT_SPOOL_MAX_ROWS", "100000"))
MQTT_MAX_INFLIGHT = int(os.environ.get("OPENAUT_MQTT_MAX_INFLIGHT", "20"))
READY_FILE = os.environ.get("OPENAUT_READY_FILE", "/var/lib/openaut/mqtt.ready")
CANONICAL_ID = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", flags=re.ASCII)


def spool_db():
    spool_dir = os.path.dirname(SPOOL)
    if spool_dir:
        os.makedirs(spool_dir, exist_ok=True)
    db = sqlite3.connect(SPOOL)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS q ("
        "topic TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL, retries INTEGER NOT NULL DEFAULT 0)"
    )
    cols = {row[1] for row in db.execute("PRAGMA table_info(q)").fetchall()}
    if "created_at" not in cols:
        db.execute("ALTER TABLE q ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
    if "retries" not in cols:
        db.execute("ALTER TABLE q ADD COLUMN retries INTEGER NOT NULL DEFAULT 0")
    db.commit()
    return db


def spool_count(db):
    return db.execute("SELECT count(*) FROM q").fetchone()[0]


def spool_payload(db, topic, body, protected_rowids=()):
    while spool_count(db) >= SPOOL_MAX_ROWS:
        protected = set(protected_rowids)
        oldest = next(
            (row for row in db.execute("SELECT rowid FROM q ORDER BY rowid") if row[0] not in protected),
            None,
        )
        if oldest is not None:
            db.execute("DELETE FROM q WHERE rowid=?", (oldest[0],))
            print("spool capacity reached; dropped oldest reading", file=sys.stderr)
        else:
            print("spool capacity reached; dropped newest reading", file=sys.stderr)
            return False
    db.execute("INSERT INTO q(topic, payload, created_at, retries) VALUES (?,?,?,0)", (topic, body, int(time.time())))
    db.commit()
    return True


def read_point(point) -> dict | None:
    """Return a normalized reading after an approved protocol integration is implemented."""
    return None


def load_config(path):
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)

    for key in ("site", "node"):
        if (
            not isinstance(cfg.get(key), str)
            or len(cfg[key]) > 63
            or not CANONICAL_ID.fullmatch(cfg[key])
        ):
            raise ValueError(f"invalid {key} identifier")
    if len(f"{cfg['site']}/{cfg['node']}") > 64:
        raise ValueError("combined site/node identity exceeds the X.509 CN limit")
    interval = cfg.get("interval_s", 15)
    if not isinstance(interval, (int, float)) or isinstance(interval, bool) or interval <= 0:
        raise ValueError("interval_s must be a positive number")
    if not isinstance(cfg.get("points"), list):
        raise ValueError("points must be a list")
    for point in cfg["points"]:
        if not isinstance(point, dict):
            raise ValueError("each point must be an object")
        for key in ("system", "metric"):
            if not isinstance(point.get(key), str) or not CANONICAL_ID.fullmatch(point[key]):
                raise ValueError(f"point has invalid {key} identifier")
        if point.get("writable", False) is not False or point.get("access", "read") != "read":
            raise ValueError("writable points are not supported by this telemetry publisher")
    return cfg


def set_ready(ready):
    if not ready:
        try:
            os.unlink(READY_FILE)
        except FileNotFoundError:
            pass
        return
    ready_dir = os.path.dirname(READY_FILE)
    if ready_dir:
        os.makedirs(ready_dir, exist_ok=True)
    temporary = f"{READY_FILE}.tmp"
    with open(temporary, "w", encoding="ascii") as handle:
        handle.write(f"{int(time.time())}\n")
    os.replace(temporary, READY_FILE)


def main():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        sys.exit("paho-mqtt unavailable; install the approved assets/requirements.lock")

    if not BROKER_HOST:
        sys.exit("EMQX_HOST not set")
    if not 1 <= BROKER_PORT <= 65535:
        sys.exit("EMQX_TLS_PORT must be between 1 and 65535")
    if SPOOL_MAX_ROWS <= 0:
        sys.exit("OPENAUT_SPOOL_MAX_ROWS must be positive")
    if MQTT_MAX_INFLIGHT <= 0:
        sys.exit("OPENAUT_MQTT_MAX_INFLIGHT must be positive")
    cfg = load_config(CFG)
    site, node = cfg["site"], cfg["node"]
    interval = cfg.get("interval_s", 15)
    status_topic = f"openaut/{site}/{node}/$status"

    set_ready(False)
    db = spool_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{site}/{node}")
    client.max_inflight_messages_set(MQTT_MAX_INFLIGHT)
    client.tls_set(
        ca_certs=f"{CERT_DIR}/ca.crt",
        certfile=f"{CERT_DIR}/{node}.crt",
        keyfile=f"{CERT_DIR}/{node}.key",
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    # An MQTT will is static; ingest records when it observes the retained offline state.
    client.will_set(status_topic, json.dumps({"value": False}), qos=1, retain=True)

    connected = threading.Event()
    events = queue.SimpleQueue()
    inflight = {}
    status_mids = set()

    def on_connect(mqtt_client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            print(f"MQTT connection rejected: {reason_code}", file=sys.stderr)
            return
        connected.set()
        info = mqtt_client.publish(
            status_topic,
            json.dumps({"value": True, "ts": int(time.time())}),
            qos=1,
            retain=True,
        )
        if info.rc == MQTT_ERR_SUCCESS:
            # Both callbacks run on Paho's network thread, so this MID is recorded before
            # on_publish can observe the corresponding PUBACK.
            status_mids.add(info.mid)

    def on_disconnect(_client, _userdata, _flags, _reason_code, _properties):
        connected.clear()
        set_ready(False)
        status_mids.clear()
        events.put(("disconnect", None))

    def on_publish(_client, _userdata, mid, _reason_code, _properties):
        if mid in status_mids:
            status_mids.remove(mid)
            set_ready(True)
            return
        events.put(("ack", mid))

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()
    next_poll = time.monotonic()

    try:
        while True:
            process_events(db, inflight, events)
            if connected.is_set():
                drain(client, db, inflight)

            now = time.monotonic()
            if now >= next_poll:
                ts = int(time.time())
                for point in cfg["points"]:
                    result = read_point(point)
                    if result is None:
                        continue
                    topic = f"openaut/{site}/{node}/{point['system']}/{point['metric']}"
                    payload = {
                        "event_id": uuid.uuid4().hex,
                        "value": result["value"],
                        "ts": ts,
                        "unit": result.get("unit", point.get("unit")),
                    }
                    spool_payload(db, topic, json.dumps(payload), inflight.values())
                next_poll = now + interval
            time.sleep(0.2)
    finally:
        set_ready(False)
        client.loop_stop()
        db.close()


def process_events(db, inflight, events):
    while True:
        try:
            event, value = events.get_nowait()
        except queue.Empty:
            break
        if event == "ack":
            rowid = inflight.pop(value, None)
            if rowid is not None:
                db.execute("DELETE FROM q WHERE rowid=?", (rowid,))
        elif event == "disconnect":
            for rowid in inflight.values():
                db.execute("UPDATE q SET retries = retries + 1 WHERE rowid=?", (rowid,))
            # Paho owns retransmission across an automatic reconnect. Keep MID mappings so a
            # later PUBACK can retire the durable row without publishing a parallel copy.
    db.commit()


def drain(client, db, inflight):
    available = MQTT_MAX_INFLIGHT - len(inflight)
    if available <= 0:
        return

    active_rowids = set(inflight.values())
    rows = db.execute("SELECT rowid, topic, payload FROM q ORDER BY rowid LIMIT 500").fetchall()
    for rowid, topic, payload in rows:
        if rowid in active_rowids:
            continue
        info = client.publish(topic, payload, qos=1)
        if info.rc != MQTT_ERR_SUCCESS:
            db.execute("UPDATE q SET retries = retries + 1 WHERE rowid=?", (rowid,))
            db.commit()
            break
        inflight[info.mid] = rowid
        available -= 1
        if available == 0:
            break


def cli():
    if len(sys.argv) == 3 and sys.argv[1] == "--check-config":
        load_config(sys.argv[2])
        return
    if len(sys.argv) != 1:
        sys.exit("usage: edge_agent.py [--check-config POINTS_JSON]")
    main()


if __name__ == "__main__":
    cli()
