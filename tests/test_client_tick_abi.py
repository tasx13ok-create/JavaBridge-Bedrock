"""Execute an unchanged authored client-only JAR against the tiny event ABI."""
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "client-tick-test-token-00000000000000000"


class ClientTickAbiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    def test_direct_client_event_jar_receives_ticks(self):
        with tempfile.TemporaryDirectory() as tmp:
            mods = Path(tmp) / "mods"
            mods.mkdir()
            source = ROOT / "out/client-tick-fixtures/client-tick.jar"
            (mods / source.name).write_bytes(source.read_bytes())
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            proc = subprocess.Popen(
                ["java", "-cp", str(ROOT / "out/host"), "bridge.Host",
                 str(mods), str(port), TOKEN, "50"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            try:
                # Host prints START messages before READY.
                lines = []
                while True:
                    line = proc.stdout.readline()
                    lines.append(line)
                    if line.startswith("READY port="):
                        break
                    self.assertTrue(line, "Host exited: " + repr(lines))
                with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
                    with client.makefile("rw", buffering=1) as wire:
                        wire.write("HELLO " + TOKEN + "\n")
                        self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                        for _ in range(2):
                            wire.write("TICK\n")
                            self.assertEqual(wire.readline().strip(), "TICK_OK handlers=2")
                        wire.write("STOP\n")
                        self.assertEqual(wire.readline().strip(), "BYE")
                out, err = proc.communicate(timeout=5)
                all_output = "".join(lines) + out
                self.assertIn("CLIENT_START 0", all_output)
                self.assertIn("CLIENT_END 1", all_output)
                self.assertIn("CLIENT_START 1", all_output)
                self.assertIn("CLIENT_END 2", all_output)
                self.assertEqual(proc.returncode, 0, err)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()


if __name__ == "__main__":
    unittest.main()
