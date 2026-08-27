import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_RELEASE = ROOT / "skills" / "edge-iot2050"
VERIFY = EDGE_RELEASE / "scripts" / "verify_bundle.py"


def load_verify():
    spec = importlib.util.spec_from_file_location("openaut_verify_bundle", VERIFY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_bundle(directory: Path):
    files = {
        "points.json": b'{"site":"lab","node":"edge-1","points":[]}',
        "edge.env": (
            "EMQX_HOST=broker.lab.invalid\n"
            "EMQX_TLS_PORT=8883\n"
            "OPENAUT_POINTS=/etc/openaut/current/points.json\n"
            "OPENAUT_CERT_DIR=/etc/openaut/current/certs\n"
            "OPENAUT_SPOOL=/var/lib/openaut/spool.sqlite\n"
            "OPENAUT_SPOOL_MAX_ROWS=100000\n"
            "OPENAUT_MQTT_MAX_INFLIGHT=20\n"
            "OPENAUT_READY_FILE=/var/lib/openaut/mqtt.ready\n"
        ).encode(),
        "ca.crt": b"test-ca",
        "node.crt": b"test-cert",
        "node.key": b"test-key",
    }
    for filename, content in files.items():
        (directory / filename).write_bytes(content)
    manifest = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {filename}\n"
        for filename, content in files.items()
    )
    (directory / "manifest.sha256").write_text(manifest, encoding="ascii")


class EdgeInstallBundleTests(unittest.TestCase):
    def test_release_manifest_matches_deployable_files(self):
        manifest = EDGE_RELEASE / "assets" / "release.sha256"
        entries = {}
        for line in manifest.read_text(encoding="ascii").splitlines():
            digest, filename = line.split("  ", 1)
            entries[filename] = digest
        self.assertEqual(
            set(entries),
            {
                "scripts/install.sh",
                "scripts/edge_agent.py",
                "scripts/verify_bundle.py",
                "assets/openaut-edge.service",
                "assets/requirements.lock",
            },
        )
        for filename, expected in entries.items():
            self.assertEqual(hashlib.sha256((EDGE_RELEASE / filename).read_bytes()).hexdigest(), expected)

    def test_valid_bundle_returns_certificate_identity(self):
        verify = load_verify()
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir)
            create_bundle(bundle)
            self.assertEqual(verify.verify_bundle(bundle, EDGE_RELEASE), "lab/edge-1")

    def test_manifest_detects_tampering(self):
        verify = load_verify()
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir)
            create_bundle(bundle)
            (bundle / "points.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify.verify_bundle(bundle, EDGE_RELEASE)

    def test_manifest_rejects_unapproved_entries(self):
        verify = load_verify()
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir)
            create_bundle(bundle)
            with (bundle / "manifest.sha256").open("a", encoding="ascii") as handle:
                handle.write(f"{'0' * 64}  extra.txt\n")
            with self.assertRaisesRegex(ValueError, "exactly the five"):
                verify.verify_bundle(bundle, EDGE_RELEASE)

    def test_bundle_rejects_extra_files_even_when_not_manifested(self):
        verify = load_verify()
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir)
            create_bundle(bundle)
            (bundle / "extra.txt").write_text("not approved", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly five files"):
                verify.verify_bundle(bundle, EDGE_RELEASE)

    def test_environment_rejects_duplicate_keys(self):
        verify = load_verify()
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir)
            create_bundle(bundle)
            with (bundle / "edge.env").open("a", encoding="utf-8") as handle:
                handle.write("EMQX_HOST=other.invalid\n")
            with self.assertRaisesRegex(ValueError, "duplicated"):
                verify.parse_env(bundle / "edge.env")


if __name__ == "__main__":
    unittest.main()
