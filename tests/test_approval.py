"""Hash approval policy is enforced before the Java class loader sees downloaded jars."""
from pathlib import Path
import hashlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "approved-jar-test-token-01234567890"


class ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")], check=True,
                       capture_output=True, text=True)

    def launch(self, approval: Path):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        host = subprocess.Popen([
            "java", "-cp", str(ROOT / "out/host"), "bridge.Host", str(ROOT / "out/mods"),
            str(port), TOKEN, "50", str(approval)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            client = None
            for _ in range(60):
                try:
                    client = socket.create_connection(("127.0.0.1", port), timeout=.3)
                    break
                except OSError:
                    if host.poll() is not None: break
                    time.sleep(.04)
            self.assertIsNotNone(client, "host did not listen")
            with client, client.makefile("rw", buffering=1) as wire:
                wire.write("HELLO " + TOKEN + "\n")
                self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                wire.write("STATUS\n")
                status = wire.readline().strip()
                wire.write("STOP\n")
                self.assertEqual(wire.readline().strip(), "BYE")
            output, errors = host.communicate(timeout=10)
            return status, output, errors
        finally:
            if host.poll() is None:
                host.kill()
                host.communicate()

    def test_explicit_hash_approved(self):
        jar = ROOT / "out/mods/hello-fabric.jar"
        sha = hashlib.sha256(jar.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "approved-mods.tsv"
            file.write_text(sha + "\t" + jar.name + "\n", encoding="utf-8")
            status, output, errors = self.launch(file)
            self.assertIn("loaded=1 skipped=0", status)

    def test_changed_hash_rejected(self):
        jar = ROOT / "out/mods/hello-fabric.jar"
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "approved-mods.tsv"
            file.write_text(("0" * 64) + "\t" + jar.name + "\n", encoding="utf-8")
            status, output, errors = self.launch(file)
            self.assertIn("loaded=0 skipped=1", status)
            self.assertIn("SHA-256 approval mismatch", errors)
            self.assertNotIn("HELLO_FABRIC_INIT", output)


if __name__ == "__main__":
    unittest.main()
