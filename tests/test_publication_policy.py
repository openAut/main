import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "skills/modbus/scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PublicationPolicy = load("publication_policy").PublicationPolicy
ReadOnlyTransport = load("readonly_transport").ReadOnlyTransport


class PublicationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.rows = []

    def policy(self, interval=60, enqueue=None):
        return PublicationPolicy(
            periodic={"temperature": interval, "last_success": 30},
            on_change={"alarm", "healthy"},
            enqueue=enqueue or (lambda *row: self.rows.append(row)),
            monotonic=lambda: self.now,
        )

    def test_fast_fc04_reads_keep_slow_publication_and_fresh_source_time(self):
        class Response:
            def isError(self):
                return False

        class Client:
            calls = 0

            def connect(self):
                return True

            def read_input_registers(self, address, *, count, device_id):
                self.calls += 1
                response = Response()
                response.registers = [200 + self.calls]
                return response

        for interval in (60, 600):
            with self.subTest(interval=interval):
                self.rows = []
                client = Client()
                transport = ReadOnlyTransport(
                    client, device_id=1, blocks={(0, 1)},
                    monotonic=lambda: self.now, wall_time=lambda: 1700000000 + self.now,
                )
                policy = self.policy(interval)
                for self.now in range(0, interval + 1, 15):
                    words = transport.read(0, 1)
                    policy.submit("temperature", words[0] / 10, transport.last_success, "degC")
                    policy.submit("last_success", transport.last_success, transport.last_success, "unix_s")
                samples = [row for row in self.rows if row[0] == "temperature"]
                self.assertEqual(client.calls, interval // 15 + 1)
                self.assertEqual(len(samples), 2)
                self.assertEqual(samples[-1], ("temperature", (200 + client.calls) / 10, 1700000000 + interval, "degC"))
                self.assertEqual(len(self.rows) - len(samples), interval // 30 + 1)

    def test_due_failed_read_does_not_create_row_and_recovery_is_due(self):
        class Client:
            def connect(self):
                return False

        policy = self.policy()
        policy.submit("temperature", 20, 1000, "degC")
        self.now = 60
        transport = ReadOnlyTransport(Client(), device_id=1, blocks={(0, 1)})
        words = transport.read(0, 1)
        if words is not None:
            policy.submit("temperature", words[0] / 10, 1060, "degC")
        self.assertEqual(len(self.rows), 1)
        self.now = 75
        self.assertTrue(policy.submit("temperature", 23, 1075, "degC"))

    def test_periodic_point_clocks_are_independent(self):
        policy = self.policy()
        policy.submit("temperature", 20, 1000, "degC")
        self.now = 15
        self.assertTrue(policy.submit("last_success", 1015, 1015, "unix_s"))
        self.now = 30
        self.assertFalse(policy.submit("last_success", 1030, 1030, "unix_s"))
        self.now = 45
        self.assertTrue(policy.submit("last_success", 1045, 1045, "unix_s"))
        self.assertFalse(policy.submit("temperature", 21, 1045, "degC"))

    def test_changes_and_recovery_bypass_periodic_gates(self):
        policy = self.policy()
        for value, expected in ((False, True), (False, False), (True, True), (False, True)):
            self.assertEqual(policy.submit("alarm", value, 1000, "bool"), expected)
        for value in (True, False, True):
            self.assertTrue(policy.submit("healthy", value, 1000, "bool"))

    def test_enqueue_failure_does_not_consume_period_or_change(self):
        def fail(*_row):
            raise OSError("spool unavailable")

        for metric, value, unit in (("temperature", 20, "degC"), ("alarm", True, "bool")):
            with self.subTest(metric=metric):
                fail_next = True

                def enqueue(*row):
                    if fail_next:
                        fail(*row)
                    self.rows.append(row)

                policy = self.policy(enqueue=enqueue)
                with self.assertRaises(OSError):
                    policy.submit(metric, value, 1000, unit)
                fail_next = False
                self.assertTrue(policy.submit(metric, value, 1000, unit))
                self.assertFalse(policy.submit(metric, value, 1000, unit))

    def test_false_enqueue_result_does_not_consume_period_or_change(self):
        for metric, value, unit in (("temperature", 20, "degC"), ("alarm", True, "bool")):
            with self.subTest(metric=metric):
                reject = True

                def enqueue(*row):
                    if reject:
                        return False
                    self.rows.append(row)

                policy = self.policy(enqueue=enqueue)
                with self.assertRaisesRegex(RuntimeError, "rejected"):
                    policy.submit(metric, value, 1000, unit)
                reject = False
                self.assertTrue(policy.submit(metric, value, 1000, unit))
                self.assertFalse(policy.submit(metric, value, 1000, unit))

    def test_slow_enqueue_starts_interval_after_durable_acceptance(self):
        for duration in (10, 90):
            with self.subTest(duration=duration):
                self.now = 0
                accepted_at = []

                def enqueue(*_row):
                    self.now += duration
                    accepted_at.append(self.now)

                policy = self.policy(enqueue=enqueue)
                self.assertTrue(policy.submit("temperature", 20, 1000, "degC"))
                self.assertFalse(policy.submit("temperature", 21, 1001, "degC"))
                self.now = duration + 59
                self.assertFalse(policy.submit("temperature", 21, 1002, "degC"))
                self.now = duration + 60
                self.assertTrue(policy.submit("temperature", 22, 1003, "degC"))
                self.assertGreaterEqual(accepted_at[1] - accepted_at[0], 60)

    def test_clock_adjustments_do_not_change_elapsed_time_gate(self):
        policy = self.policy()
        policy.submit("temperature", 20, 1000, "degC")
        self.now = 59
        self.assertFalse(policy.submit("temperature", 21, 99999, "degC"))
        self.now = 60
        self.assertTrue(policy.submit("temperature", 22, 500, "degC"))
        self.assertEqual(self.rows[-1][2], 500)

    def test_restart_emits_snapshot_and_no_catchup_history(self):
        policy = self.policy()
        policy.submit("temperature", 20, 1000, "degC")
        self.now = 3600
        policy.submit("temperature", 22, 4600, "degC")
        self.assertEqual(len(self.rows), 2)
        self.assertTrue(self.policy().submit("temperature", 22, 4600, "degC"))

    def test_invalid_profiles_fail_before_enqueue(self):
        for interval in (0, -1, True, float("nan"), float("inf"), "30", None):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                self.policy(interval)
        for periodic, changes in (({}, set()), ({"alarm": 30}, {"alarm"}), ({"": 30}, set())):
            with self.assertRaises(ValueError):
                PublicationPolicy(periodic=periodic, on_change=changes, enqueue=lambda *_: None)
        with self.assertRaises(ValueError):
            self.policy().submit("unknown", 1, 1000, "code")
        self.assertEqual(self.rows, [])


if __name__ == "__main__":
    unittest.main()
