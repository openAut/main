import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_vendor", ROOT / "scripts/build_edge_vendor.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
VERIFY = ROOT / "scripts/verify_edge_vendor.py"


class EdgeVendorTests(unittest.TestCase):
    def run_verify(self, vendor, module, env=None):
        return subprocess.run([sys.executable, str(VERIFY), str(vendor), module],
                              capture_output=True, text=True, env=env)

    def test_missing_dependency_cannot_fall_back_to_pythonpath(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vendor, ambient = root / "vendor", root / "ambient"
            vendor.mkdir()
            ambient.mkdir()
            (ambient / "ambient_only.py").write_text("VALUE = 1\n")
            env = os.environ | {"PYTHONPATH": str(ambient)}
            result = self.run_verify(vendor, "ambient_only", env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ModuleNotFoundError", result.stderr)

    def test_import_from_vendor_succeeds_without_bytecode(self):
        with tempfile.TemporaryDirectory() as temporary:
            vendor = Path(temporary)
            (vendor / "edge_probe.py").write_text("VALUE = 1\n")
            result = self.run_verify(vendor, "edge_probe")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("EDGE_VENDOR_OK", result.stdout)
            self.assertFalse((vendor / "__pycache__").exists())

    def test_offline_build_verifies_hash_and_preserves_existing_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheels = root / "wheels"
            wheels.mkdir()
            wheel = wheels / "edge_probe-1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("edge_probe.py", "VALUE = 42\n")
                archive.writestr("edge_probe-1.0.dist-info/METADATA",
                                 "Metadata-Version: 2.1\nName: edge-probe\nVersion: 1.0\n")
                archive.writestr("edge_probe-1.0.dist-info/WHEEL",
                                 "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                archive.writestr("edge_probe-1.0.dist-info/RECORD", "")
            lock = root / "requirements.lock"
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            lock.write_text(f"edge-probe==1.0 --hash=sha256:{digest}\n")
            output = root / "vendor"
            ambient = root / "ambient"
            ambient.mkdir()
            marker = root / "ambient-executed"
            (ambient / "sitecustomize.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
            )
            with patch.dict(os.environ, {"PYTHONPATH": str(ambient)}):
                BUILDER.build(lock, wheels, output)
            self.assertFalse(marker.exists(), "pip executed ambient sitecustomize")
            self.assertEqual(self.run_verify(output, "edge_probe").returncode, 0)
            with self.assertRaises(ValueError):
                BUILDER.build(lock, wheels, output)
            original = (output / "edge_probe.py").read_bytes()
            lock.write_text("edge-probe==1.0 --hash=sha256:" + "0" * 64 + "\n")
            with self.assertRaises(subprocess.CalledProcessError):
                BUILDER.build(lock, wheels, root / "bad-vendor")
            self.assertFalse((root / "bad-vendor").exists())
            self.assertEqual((output / "edge_probe.py").read_bytes(), original)

    def test_remote_lock_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "probe-1.0-py3-none-any.whl").touch()
            lock = root / "requirements.lock"
            lock.write_text("probe @ https://example.invalid/probe.whl\n")
            with self.assertRaises(ValueError):
                BUILDER.build(lock, root, root / "vendor")

    def test_mislabeled_wheels_are_rejected_before_pip(self):
        cases = [
            ("true", "py3-none-any", "probe/native.so"),
            ("true", "py3-none-any", "probe/native.PYD"),
            ("true", "py3-none-any", "probe/native.dll"),
            ("false", "py3-none-any", None),
            ("true", "cp312-cp312-linux_x86_64", None),
        ]
        for pure, tag, native in cases:
            with self.subTest(pure=pure, tag=tag, native=native), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                wheel = root / "probe-1.0-py3-none-any.whl"
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr("probe-1.0.dist-info/WHEEL",
                                     f"Wheel-Version: 1.0\nRoot-Is-Purelib: {pure}\nTag: {tag}\n")
                    if native:
                        archive.writestr(native, b"native placeholder")
                lock = root / "requirements.lock"
                lock.write_text("probe==1.0 --hash=sha256:" + hashlib.sha256(wheel.read_bytes()).hexdigest())
                with patch.object(BUILDER.subprocess, "run") as pip:
                    with self.assertRaises(ValueError):
                        BUILDER.build(lock, root, root / "vendor")
                    pip.assert_not_called()
                self.assertFalse((root / "vendor").exists())

    def test_symlink_vendor_root_is_rejected_in_both_cli_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vendor, link = root / "vendor", root / "vendor-link"
            vendor.mkdir()
            (vendor / "edge_probe.py").write_text("VALUE = 1\n")
            try:
                link.symlink_to(vendor, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            for flags in ([], ["-I", "-S"]):
                with self.subTest(flags=flags):
                    result = subprocess.run(
                        [sys.executable, *flags, str(VERIFY), str(link), "edge_probe"],
                        capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("vendor root must not be a symlink", result.stderr)
