"""Sidecar distribution should be deterministic and must not ship credentials."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    def test_package_contains_runtime_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "a.zip"
            second = Path(directory) / "b.zip"
            for output in (first, second):
                subprocess.run([sys.executable, str(ROOT / "tools/package_runtime.py"),
                                "--output", str(output)],
                               check=True, capture_output=True, text=True)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                             hashlib.sha256(second.read_bytes()).digest())
            with ZipFile(first) as archive:
                names = archive.namelist()
                self.assertTrue(any(name.endswith("out/host/bridge/Host.class")
                                    for name in names))
                self.assertTrue(any(name.endswith("out/mods/hello-fabric.jar")
                                    for name in names))
                self.assertTrue(any(name.endswith("tools/start_client_bridge.py")
                                    for name in names))
                self.assertFalse(any("session.conf" in name for name in names))
                self.assertFalse(any(name.endswith(".exe") or name.endswith(".dll")
                                     for name in names))


if __name__ == "__main__":
    unittest.main()
