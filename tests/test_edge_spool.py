import importlib.util
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

    def test_drain_increments_retries_on_publish_failure(self):
        edge = load_edge()
        db = memory_spool()
        db.execute("INSERT INTO q(topic, payload, created_at, retries) VALUES ('t/1', '{}', 1, 0)")

        class Client:
            def publish(self, _topic, _payload, qos=0):
                class Info:
                    rc = 1

                return Info()

        edge.drain(Client(), db)

        self.assertEqual(db.execute("SELECT retries FROM q").fetchone()[0], 1)

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


if __name__ == "__main__":
    unittest.main()
