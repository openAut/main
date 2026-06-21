#!/usr/bin/env python3
"""openAut IOT2050 edge agent (reference).

Polls field points from a point map, publishes to EMQX over mutual TLS using the node's client
certificate, and uses a local SQLite spool for store-and-forward when the broker is unreachable.

This stub focuses on the MQTT/TLS + spool contract. Field reads are stubbed: wire `read_point()`
to the modbus/bacnet/m-bus protocol skills for your hardware.

Reads /etc/openaut/points.json (site, node, interval_s, points[]).
Certs at /etc/openaut/certs/{ca.crt, <node>.crt, <node>.key}. Not production-hardened.
"""
import json
import os
import sqlite3
import ssl
import sys
import time

CFG = os.environ.get("OPENAUT_POINTS", "/etc/openaut/points.json")
CERT_DIR = os.environ.get("OPENAUT_CERT_DIR", "/etc/openaut/certs")
BROKER_HOST = os.environ.get("EMQX_HOST")
BROKER_PORT = int(os.environ.get("EMQX_TLS_PORT", "8883"))
SPOOL = os.environ.get("OPENAUT_SPOOL", "/var/lib/openaut/spool.sqlite")
SPOOL_MAX_ROWS = int(os.environ.get("OPENAUT_SPOOL_MAX_ROWS", "100000"))


def spool_db():
    spool_dir = os.path.dirname(SPOOL)
    if spool_dir:
        os.makedirs(spool_dir, exist_ok=True)
    db = sqlite3.connect(SPOOL)
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


def spool_payload(db, topic, body):
    if spool_count(db) >= SPOOL_MAX_ROWS:
        oldest = db.execute("SELECT rowid FROM q ORDER BY rowid LIMIT 1").fetchone()
        if oldest:
            db.execute("DELETE FROM q WHERE rowid=?", (oldest[0],))
    db.execute("INSERT INTO q(topic, payload, created_at, retries) VALUES (?,?,?,0)", (topic, body, int(time.time())))
    db.commit()


def read_point(point) -> dict | None:
    """STUB — return {"value":..., "unit":...}. Wire to modbus/bacnet/m-bus skills here."""
    return None  # replace with a real field read


def main():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        sys.exit("pip install paho-mqtt")

    if not BROKER_HOST:
        sys.exit("EMQX_HOST not set")
    with open(CFG) as fh:
        cfg = json.load(fh)
    site, node = cfg["site"], cfg["node"]
    interval = cfg.get("interval_s", 15)
    status_topic = f"openaut/{site}/{node}/$status"

    db = spool_db()
    client = mqtt.Client(client_id=node)
    client.tls_set(
        ca_certs=f"{CERT_DIR}/ca.crt",
        certfile=f"{CERT_DIR}/{node}.crt",
        keyfile=f"{CERT_DIR}/{node}.key",
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    # Last-Will so the AI tier sees this node drop offline.
    client.will_set(status_topic, json.dumps({"value": False, "ts": int(time.time())}), qos=1, retain=True)

    connected = {"ok": False}
    client.on_connect = lambda *_: (connected.update(ok=True),
                                    client.publish(status_topic,
                                                   json.dumps({"value": True, "ts": int(time.time())}),
                                                   qos=1, retain=True))
    client.on_disconnect = lambda *_: connected.update(ok=False)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except OSError as exc:
        print(f"initial connect failed ({exc}); will spool and retry", file=sys.stderr)
    client.loop_start()

    def emit(topic, payload):
        body = json.dumps(payload)
        if connected["ok"]:
            drain(client, db)                      # flush backlog first (ordering)
            info = client.publish(topic, body, qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                spool_payload(db, topic, body)
        else:
            spool_payload(db, topic, body)

    while True:
        ts = int(time.time())
        for p in cfg["points"]:
            r = read_point(p)
            if r is None:
                continue
            topic = f"openaut/{site}/{node}/{p['system']}/{p['metric']}"
            emit(topic, {"value": r["value"], "ts": ts, "unit": r.get("unit", p.get("unit"))})
        time.sleep(interval)


def drain(client, db):
    rows = db.execute("SELECT rowid, topic, payload FROM q ORDER BY rowid LIMIT 500").fetchall()
    for rowid, topic, payload in rows:
        info = client.publish(topic, payload, qos=1)
        if info.rc == 0:
            db.execute("DELETE FROM q WHERE rowid=?", (rowid,))
        else:
            db.execute("UPDATE q SET retries = retries + 1 WHERE rowid=?", (rowid,))
    db.commit()


if __name__ == "__main__":
    main()
