"""Verify that a .jar importing real Fabric package names loads and receives ticks."""
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "fabric-shim-test-token-123456789"


class FabricApiShimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")], check=True,
                       capture_output=True, text=True)

    def test_fabric_event_abi_on_a_direct_jar(self):
        with socket.socket() as temp:
            temp.bind(("127.0.0.1", 0))
            port = temp.getsockname()[1]
        process = subprocess.Popen([
            "java", "-cp", str(ROOT / "out/host"), "bridge.Host",
            str(ROOT / "out/fixtures"), str(port), TOKEN, "20"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            connection = None
            for _ in range(60):
                try:
                    connection = socket.create_connection(("127.0.0.1", port), timeout=1)
                    break
                except OSError:
                    time.sleep(.05)
            self.assertIsNotNone(connection)
            with connection, connection.makefile("rw", buffering=1) as wire:
                wire.write("HELLO " + TOKEN + "\n")
                self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                wire.write("STATUS\n")
                self.assertEqual(wire.readline().strip(), "STATUS loaded=1 skipped=0 handlers=0")
                for _ in range(3):
                    wire.write("TICK\n")
                    self.assertEqual(wire.readline().strip(), "TICK_OK handlers=1")
                wire.write("STOP\n")
                self.assertEqual(wire.readline().strip(), "BYE")
            out, err = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 0, err)
            self.assertIn("FABRIC_API_LISTENER_REGISTERED", out)
            self.assertIn("FABRIC_API_TICK 3", out)
            self.assertIn("FABRIC_LOADER_SELF=true", out)
            self.assertIn("FABRIC_FACTORY_EVENT=ok", out)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()
