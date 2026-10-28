"""Verify that a client-only Fabric JAR can initialize in the sidecar."""
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "client-only-test-token-123456789"

class ClientOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")], check=True,
                       capture_output=True, text=True)

    def test_client_entrypoint(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        host = subprocess.Popen(["java", "-cp", str(ROOT / "out/host"), "bridge.Host",
                                 str(ROOT / "out/client-fixtures"), str(port), TOKEN, "10"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            conn = None
            for _ in range(80):
                try:
                    conn = socket.create_connection(("127.0.0.1", port), timeout=.3)
                    break
                except OSError:
                    time.sleep(.05)
            self.assertIsNotNone(conn)
            with conn, conn.makefile("rw", buffering=1) as wire:
                wire.write("HELLO " + TOKEN + "\n")
                self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                wire.write("STATUS\n")
                self.assertEqual(wire.readline().strip(), "STATUS loaded=1 skipped=0 handlers=1")
                wire.write("TICK\n")
                self.assertEqual(wire.readline().strip(), "TICK_OK handlers=1")
                wire.write("STOP\n")
                self.assertEqual(wire.readline().strip(), "BYE")
            output, errors = host.communicate(timeout=10)
            self.assertEqual(host.returncode, 0, errors)
            self.assertIn("CLIENT_ONLY_INITIALIZED", output)
            self.assertIn("CLIENT_ONLY_TICK", output)
        finally:
            if host.poll() is None:
                host.kill()
                host.communicate()
if __name__ == "__main__": unittest.main()
