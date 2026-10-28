"""Reject malformed Java-to-native frames without dispatching unsafe log text."""
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "native-security-test-token-00000000000000"


@unittest.skipUnless(sys.platform.startswith("linux"), "Uses the Linux native harness toolchain")
class NativeSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = ROOT / "out" / "security_harness"
        cls.exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "g++", "-std=c++20", "-O0", "-pthread",
            "-I", str(ROOT / "native/levilamina-client/src"),
            str(ROOT / "native/levilamina-client/src/mod/BridgeTransport.cpp"),
            str(ROOT / "native/test/transport_harness.cpp"),
            "-o", str(cls.exe)
        ], capture_output=True, text=True, check=True)

    def test_unsafe_control_character_log_frame_rejected(self):
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(2)
            server.settimeout(5)
            port = server.getsockname()[1]
            errors = []

            def fake_host():
                try:
                    with server.accept()[0] as client:
                        client.settimeout(4)
                        with client.makefile("rwb", buffering=0) as wire:
                            token = wire.readline().decode("utf-8").strip()
                            assert token == "HELLO " + TOKEN, token
                            wire.write(b"OK bridge-v0\n")
                            event = wire.readline()
                            assert event in (b"JOIN\n", b"TICK\n", b"LEAVE\n"), event
                            # 0A decodes to a newline character: must not be logged.
                            wire.write(b"ACTION LOG 0a\n")
                except Exception as exc:
                    errors.append(str(exc))

            with tempfile.TemporaryDirectory() as home:
                path = Path(home) / ".config" / "CFBedrockJavaBridge" / "session.conf"
                path.parent.mkdir(parents=True)
                path.write_text(f"PORT {port}\nTOKEN {TOKEN}\n", encoding="utf-8")
                path.chmod(0o600)
                thread = threading.Thread(target=fake_host, daemon=True)
                thread.start()
                p = subprocess.run([str(self.exe)], env={**os.environ, "HOME": home},
                                   capture_output=True, text=True, timeout=12)
                thread.join(timeout=4)
            self.assertEqual(errors, [])
            self.assertNotEqual(p.returncode, 0)
            self.assertRegex(p.stdout, r"RELAY_DROPPED=[1-9][0-9]*")
            self.assertNotIn("LOG_RELAY=", p.stdout)


if __name__ == "__main__":
    unittest.main()
