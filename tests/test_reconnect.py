"""The production Java sidecar must survive a dropped client session."""
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "reconnect-test-local-token-000000000000000"


class ReconnectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    def test_bad_auth_and_disconnect_do_not_kill_reconnectable_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            trust = folder / "approved-mods.tsv"
            trust.write_text("# no user mods in this reconnect test\n", encoding="utf-8")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            proc = subprocess.Popen([
                "java", "-cp", str(ROOT / "out/host"),
                "bridge.Host", str(folder), str(port), TOKEN, "50",
                str(trust), "--reconnect"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertIn("READY port=", proc.stdout.readline())
                with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
                    with c.makefile("rw", buffering=1) as wire:
                        wire.write("HELLO wrong\n")
                        self.assertEqual(wire.readline().strip(), "ERROR unauthorized")
                self.assertIsNone(proc.poll())
                with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
                    with c.makefile("rw", buffering=1) as wire:
                        wire.write("HELLO " + TOKEN + "\n")
                        self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                        wire.write("TICK\n")
                        self.assertEqual(wire.readline().strip(), "TICK_OK handlers=0")
                self.assertIsNone(proc.poll())
                with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
                    with c.makefile("rw", buffering=1) as wire:
                        wire.write("HELLO " + TOKEN + "\n")
                        self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                        wire.write("STOP\n")
                        self.assertEqual(wire.readline().strip(), "BYE")
                out, err = proc.communicate(timeout=5)
                self.assertEqual(proc.returncode, 0, err + out)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()


if __name__ == "__main__":
    unittest.main()
