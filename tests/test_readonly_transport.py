import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


PATH = Path(__file__).resolve().parents[1] / "skills/modbus/scripts/readonly_transport.py"
SPEC = importlib.util.spec_from_file_location("readonly_transport", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Client:
    def __init__(self):
        self.connect_calls = self.close_calls = self.read_calls = 0
        self.connect_error = None
        self.connect_result = True
        self.read_error = None
        self.close_error = None
        self.response = SimpleNamespace(isError=lambda: False, registers=[215])

    def connect(self):
        self.connect_calls += 1
        if self.connect_error:
            raise self.connect_error
        return self.connect_result

    def close(self):
        self.close_calls += 1
        if self.close_error:
            raise self.close_error

    def read_input_registers(self, address, *, count, device_id):
        self.read_calls += 1
        if self.read_error:
            raise self.read_error
        return self.response


class ReadOnlyTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.clock = {"mono": 10, "wall": 1700000000}
        self.reader = MODULE.ReadOnlyTransport(
            self.client, device_id=1, blocks=[(16, 1)],
            monotonic=lambda: self.clock["mono"], wall_time=lambda: self.clock["wall"],
        )

    def test_unknown_block_never_connects_or_reads(self):
        with self.assertRaises(ValueError):
            self.reader.read(17, 1)
        self.assertEqual(self.client.connect_calls, 0)
        self.assertEqual(self.client.read_calls, 0)

    def test_no_fabricated_success_before_first_read(self):
        self.assertFalse(self.reader.health()["field_protocol_healthy"])
        self.assertNotIn("field_protocol_last_success_unixtime", self.reader.health())

    def test_reopen_after_three_exceptions_then_success_without_process_restart(self):
        self.client.read_error = OSError(5, "serial I/O")
        for _ in range(2):
            self.assertIsNone(self.reader.read(16, 1))
        self.assertEqual(self.client.close_calls, 0)
        self.reader.read(16, 1)
        self.assertEqual(self.client.close_calls, 1)
        self.assertFalse(self.reader.connected)
        self.client.read_error = None
        self.assertEqual(self.reader.read(16, 1), [215])
        self.assertEqual(self.client.connect_calls, 2)
        self.assertTrue(self.reader.health()["field_protocol_healthy"])
        self.assertEqual(self.reader.consecutive_errors, 0)

    def test_device_errors_do_not_reopen_or_report_success(self):
        self.client.response.isError = lambda: True
        for _ in range(5):
            self.assertIsNone(self.reader.read(16, 1))
        self.assertEqual(self.client.close_calls, 0)
        self.assertEqual(self.reader.consecutive_errors, 5)
        self.assertFalse(self.reader.health()["field_protocol_healthy"])

    def test_success_resets_exception_streak(self):
        self.client.read_error = OSError("broken")
        self.reader.read(16, 1)
        self.client.read_error = None
        self.reader.read(16, 1)
        self.client.read_error = OSError("broken again")
        for _ in range(2):
            self.reader.read(16, 1)
        self.assertEqual(self.client.close_calls, 0)

    def test_failed_connect_and_close_are_recoverable(self):
        self.client.connect_error = OSError("unavailable")
        self.client.close_error = OSError("already closed")
        for _ in range(3):
            self.assertIsNone(self.reader.read(16, 1))
        self.assertEqual(self.client.read_calls, 0)
        self.client.connect_error = None
        self.assertEqual(self.reader.read(16, 1), [215])

    def test_false_connect_does_not_read(self):
        self.client.connect_result = False
        self.assertIsNone(self.reader.read(16, 1))
        self.assertEqual(self.client.read_calls, 0)

    def test_wall_clock_jump_does_not_extend_freshness(self):
        self.reader.read(16, 1)
        self.clock["wall"] -= 3600
        self.clock["mono"] = 71
        self.assertFalse(self.reader.health()["field_protocol_healthy"])
        self.assertEqual(self.reader.health()["field_protocol_last_success_unixtime"], 1700000000)

    def test_short_or_invalid_response_is_not_success(self):
        for words in ([], [1, 2], [True], [-1], [65536]):
            with self.subTest(words=words):
                self.client.response.registers = words
                self.assertIsNone(self.reader.read(16, 1))
                self.assertIsNone(self.reader.last_success)

    def test_invalid_profile_is_rejected(self):
        for kwargs in ({"device_id": 0}, {"blocks": []}, {"blocks": [(65535, 2)]},
                       {"reopen_after": 0}, {"stale_after": float("nan")}):
            values = {"device_id": 1, "blocks": [(16, 1)]} | kwargs
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MODULE.ReadOnlyTransport(self.client, **values)
