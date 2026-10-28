"""A malformed event ACK must not be accepted as a successful Bedrock relay."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "ack-protocol-test-token-00000000000000"


@unittest.skipUnless(sys.platform.startswith("linux"), "Native C++ harness uses Linux compiler")
class AckGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable = ROOT / "out" / "ack_harness"
        cls.executable.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "g++", "-std=c++20", "-O0", "-pthread",
            "-I", str(ROOT / "native/levilamina-client/src"),
            str(ROOT / "native/levilamina-client/src/mod/BridgeTransport.cpp"),
            str(ROOT / "native/test/transport_harness.cpp"),
            "-o", str(cls.executable)
        ], check=True, capture_output=True, text=True)

    def test_forged_ack_suffix_is_rejected(self):
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            server.settimeout(5)
            port = server.getsockname()[1]
            seen = []
            errors = []

            def fake_sidecar():
                try:
                    with server.accept()[0] as client:
                        client.settimeout(3)
                        with client.makefile("rwb", buffering=0) as wire:
                            seen.append(wire.readline().decode().strip())
                            wire.write(b"OK bridge-v0\n")
                            seen.append(wire.readline().decode().strip())
                            wire.write(b"JOIN_OKgarbage handlers=1\n")
                except Exception as exc:
                    errors.append(repr(exc))

            with tempfile.TemporaryDirectory() as home:
                cfg = Path(home) / ".config" / "CFBedrockJavaBridge" / "session.conf"
                cfg.parent.mkdir(parents=True)
                cfg.write_text(f"PORT {port}\nTOKEN {TOKEN}\n", encoding="utf-8")
                cfg.chmod(0o600)
                thread = threading.Thread(target=fake_sidecar, daemon=True)
                thread.start()
                process = subprocess.run([str(self.executable)],
                    env={**os.environ, "HOME": home},
                    capture_output=True, text=True, timeout=12)
                thread.join(timeout=3)
            self.assertEqual(errors, [])
            self.assertEqual(seen[:2], ["HELLO " + TOKEN, "JOIN"])
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("RELAY_DROPPED=", process.stdout)
            dropped = int(process.stdout.rsplit("RELAY_DROPPED=", 1)[1].splitlines()[0])
            self.assertGreaterEqual(dropped, 1)


if __name__ == "__main__":
    unittest.main()
