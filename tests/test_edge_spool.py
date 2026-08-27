import importlib.util
import os
import queue
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "skills" / "edge-iot2050" / "scripts" / "edge_agent.py"


def load_edge():
    spec = importlib.util.spec_from_file_location("openaut_edge_agent", EDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def memory_spool():
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE q ("
        "topic TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL, retries INTEGER NOT NULL DEFAULT 0)"
    )
    return db


class EdgeSpoolTests(unittest.TestCase):
    def test_spool_payload_caps_rows(self):
        edge = load_edge()
        db = memory_spool()
        original_max = edge.SPOOL_MAX_ROWS
        edge.SPOOL_MAX_ROWS = 2
        try:
            edge.spool_payload(db, "t/1", "{}")
            edge.spool_payload(db, "t/2", "{}")
            edge.spool_payload(db, "t/3", "{}")
        finally:
            edge.SPOOL_MAX_ROWS = original_max

        rows = db.execute("SELECT topic, retries FROM q ORDER BY rowid").fetchall()
        self.assertEqual(rows, [("t/2", 0), ("t/3", 0)])

    def test_spool_drops_newest_when_all_rows_are_inflight(self):
        edge = load_edge()
        db = memory_spool()
        original_max = edge.SPOOL_MAX_ROWS
        edge.SPOOL_MAX_ROWS = 1
        try:
            edge.spool_payload(db, "t/1", "{}")
            inserted = edge.spool_payload(db, "t/2", "{}", protected_rowids={1})
        finally:
            edge.SPOOL_MAX_ROWS = original_max

        self.assertFalse(inserted)
        self.assertEqual(db.execute("SELECT topic FROM q").fetchall(), [("t/1",)])

    def test_spool_enforces_a_reduced_limit(self):
        edge = load_edge()
        db = memory_spool()
        for index in range(3):
            db.execute(
                "INSERT INTO q(topic, payload, created_at, retries) VALUES (?,?,1,0)",
                (f"t/{index}", "{}"),
            )
        original_max = edge.SPOOL_MAX_ROWS
        edge.SPOOL_MAX_ROWS = 2
        try:
            edge.spool_payload(db, "t/new", "{}")
        finally:
            edge.SPOOL_MAX_ROWS = original_max

        self.assertEqual(db.execute("SELECT topic FROM q ORDER BY rowid").fetchall(), [("t/2",), ("t/new",)])

    def test_drain_increments_retries_on_publish_failure(self):
        edge = load_edge()
        db = memory_spool()
        db.execute("INSERT INTO q(topic, payload, created_at, retries) VALUES ('t/1', '{}', 1, 0)")

        class Client:
            def publish(self, _topic, _payload, qos=0):
                class Info:
                    rc = 1

                return Info()

        edge.drain(Client(), db, {})

        self.assertEqual(db.execute("SELECT retries FROM q").fetchone()[0], 1)

    def test_drain_keeps_row_until_puback(self):
        edge = load_edge()
        db = memory_spool()
        db.execute("INSERT INTO q(topic, payload, created_at, retries) VALUES ('t/1', '{}', 1, 0)")

        class Client:
            def publish(self, _topic, _payload, qos=0):
                class Info:
                    rc = edge.MQTT_ERR_SUCCESS
                    mid = 42

                return Info()

        inflight = {}
        edge.drain(Client(), db, inflight)

        self.assertEqual(db.execute("SELECT count(*) FROM q").fetchone()[0], 1)
        self.assertEqual(inflight, {42: 1})

        events = queue.SimpleQueue()
        events.put(("ack", 42))
        edge.process_events(db, inflight, events)

        self.assertEqual(db.execute("SELECT count(*) FROM q").fetchone()[0], 0)
        self.assertEqual(inflight, {})

    def test_disconnect_leaves_unacknowledged_row_with_paho(self):
        edge = load_edge()
        db = memory_spool()
        db.execute("INSERT INTO q(topic, payload, created_at, retries) VALUES ('t/1', '{}', 1, 0)")
        inflight = {42: 1}
        events = queue.SimpleQueue()
        events.put(("disconnect", None))

        edge.process_events(db, inflight, events)

        self.assertEqual(db.execute("SELECT retries FROM q").fetchone()[0], 1)
        self.assertEqual(inflight, {42: 1})

    def test_spool_db_migrates_legacy_queue(self):
        edge = load_edge()
        original_spool = edge.SPOOL
        with tempfile.TemporaryDirectory() as tmpdir:
            spool = str(Path(tmpdir) / "spool.sqlite")
            db = sqlite3.connect(spool)
            db.execute("CREATE TABLE q (topic TEXT, payload TEXT)")
            db.commit()
            db.close()

            edge.SPOOL = spool
            try:
                migrated = edge.spool_db()
                cols = {row[1] for row in migrated.execute("PRAGMA table_info(q)").fetchall()}
                migrated.close()
            finally:
                edge.SPOOL = original_spool

        self.assertEqual(cols, {"topic", "payload", "created_at", "retries"})

    def test_config_rejects_writable_points(self):
        edge = load_edge()
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "points.json"
            config.write_text(
                '{"site":"lab","node":"edge-1","points":['
                '{"system":"ahu","metric":"setpoint","writable":true}]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "writable points"):
                edge.load_config(config)

    def test_config_rejects_non_boolean_writable_marker(self):
        edge = load_edge()
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "points.json"
            config.write_text(
                '{"site":"lab","node":"edge-1","points":['
                '{"system":"ahu","metric":"setpoint","writable":1}]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "writable points"):
                edge.load_config(config)

    def test_config_enforces_certificate_identity_constraints(self):
        edge = load_edge()
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "points.json"
            config.write_text(
                '{"site":"UPPER","node":"edge-1","points":[]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "invalid site"):
                edge.load_config(config)

    def test_ready_file_is_created_and_removed(self):
        edge = load_edge()
        original = edge.READY_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            ready = Path(tmpdir) / "mqtt.ready"
            edge.READY_FILE = str(ready)
            try:
                edge.set_ready(True)
                self.assertTrue(ready.read_text(encoding="ascii").strip().isdigit())
                edge.set_ready(False)
                self.assertFalse(ready.exists())
            finally:
                edge.READY_FILE = original

    def test_cli_config_check_does_not_start_runtime(self):
        edge = load_edge()
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "points.json"
            config.write_text('{"site":"lab","node":"edge-1","points":[]}', encoding="utf-8")
            original_argv = os.sys.argv
            os.sys.argv = [str(EDGE), "--check-config", str(config)]
            try:
                edge.cli()
            finally:
                os.sys.argv = original_argv


if __name__ == "__main__":
    unittest.main()
