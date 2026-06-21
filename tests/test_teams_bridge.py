import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridges" / "teams-webhook" / "teams_bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("openaut_teams_bridge", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TeamsBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load_bridge()

    def test_content_length_parse_accepts_missing_and_numeric_values(self):
        self.assertEqual(self.bridge.parse_content_length(None), 0)
        self.assertEqual(self.bridge.parse_content_length("42"), 42)

    def test_content_length_parse_rejects_malformed_values(self):
        self.assertIsNone(self.bridge.parse_content_length("not-a-number"))


if __name__ == "__main__":
    unittest.main()
