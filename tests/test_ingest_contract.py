import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "skills" / "timeseries-stack" / "scripts" / "ingest.py"


def load_ingest():
    spec = importlib.util.spec_from_file_location("openaut_ingest", INGEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IngestContractTests(unittest.TestCase):
    def setUp(self):
        self.ingest = load_ingest()

    def test_parse_telemetry_topic(self):
        self.assertEqual(
            self.ingest.parse_topic("openaut/karsamala/iot2050-ahu-01/ahu/supply_temp"),
            ("karsamala", "iot2050-ahu-01", "ahu", "supply_temp"),
        )

    def test_status_topic_is_separate_contract(self):
        self.assertIsNone(self.ingest.parse_topic("openaut/karsamala/iot2050-ahu-01/$status"))
        self.assertEqual(
            self.ingest.parse_status_topic("openaut/karsamala/iot2050-ahu-01/$status"),
            ("karsamala", "iot2050-ahu-01"),
        )

    def test_numeric_payload_maps_to_value_only(self):
        row = self.ingest.telemetry_row(
            "openaut/karsamala/iot2050-ahu-01/ahu/supply_temp",
            json.dumps({"value": 21.5, "ts": 1700000000, "unit": "degC"}).encode(),
        )
        self.assertEqual(row["value"], 21.5)
        self.assertIsNone(row["bool_val"])
        self.assertIsNone(row["event_id"])

    def test_event_id_is_preserved_for_deduplication(self):
        event_id = "0123456789abcdef0123456789abcdef"
        row = self.ingest.telemetry_row(
            "openaut/karsamala/iot2050-ahu-01/ahu/supply_temp",
            json.dumps({"event_id": event_id, "value": 21.5, "ts": 1700000000}).encode(),
        )
        self.assertEqual(row["event_id"], event_id)

    def test_invalid_event_id_is_rejected(self):
        self.assertIsNone(
            self.ingest.telemetry_row(
                "openaut/karsamala/iot2050-ahu-01/ahu/supply_temp",
                json.dumps({"event_id": "not-canonical", "value": 21.5, "ts": 1700000000}).encode(),
            )
        )

    def test_bool_payload_maps_to_bool_only(self):
        row = self.ingest.telemetry_row(
            "openaut/karsamala/iot2050-ahu-01/ahu/fan_status",
            json.dumps({"value": True, "ts": 1700000000, "unit": "bool"}).encode(),
        )
        self.assertIsNone(row["value"])
        self.assertIs(row["bool_val"], True)

    def test_invalid_payloads_are_ignored(self):
        self.assertIsNone(self.ingest.telemetry_row("openaut/karsamala/iot2050-ahu-01/ahu/supply_temp", b"{"))
        self.assertIsNone(
            self.ingest.telemetry_row("openaut/karsamala/iot2050-ahu-01/ahu/supply_temp", b'{"value":1}')
        )

    def test_status_payload_requires_bool(self):
        row = self.ingest.status_row(
            "openaut/karsamala/iot2050-ahu-01/$status",
            json.dumps({"value": False, "ts": 1700000000}).encode(),
        )
        self.assertEqual(
            row,
            {"site": "karsamala", "node": "iot2050-ahu-01", "online": False, "ts": 1700000000},
        )
        self.assertIsNone(
            self.ingest.status_row("openaut/karsamala/iot2050-ahu-01/$status", b'{"value":"false","ts":1}')
        )

    def test_offline_will_uses_broker_receipt_time(self):
        row = self.ingest.status_row(
            "openaut/karsamala/iot2050-ahu-01/$status",
            b'{"value":false}',
            received_at=1700000001,
        )
        self.assertEqual(row["ts"], 1700000001)
        self.assertIs(row["online"], False)

    def test_online_status_still_requires_source_timestamp(self):
        self.assertIsNone(
            self.ingest.status_row(
                "openaut/karsamala/iot2050-ahu-01/$status",
                b'{"value":true}',
                received_at=1700000001,
            )
        )


if __name__ == "__main__":
    unittest.main()
