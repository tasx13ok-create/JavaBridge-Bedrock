"""Windows-only smoke test: native MSVC-built relay -> real Java host."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "windows-smoke-local-token-00000000000000"


@unittest.skipUnless(os.name == "nt", "Windows smoke test requires native .exe")
class WindowsRelaySmoke(unittest.TestCase):
    def test_native_windows_events_reach_java(self):
        executable = ROOT / "out" / "transport_harness.exe"
        self.assertTrue(executable.exists(), "Build the C++ harness first")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as localappdata:
            path = Path(localappdata) / "CFBedrockJavaBridge" / "session.conf"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"PORT {port}\nTOKEN {TOKEN}\n", encoding="utf-8")
            env = {**os.environ, "LOCALAPPDATA": localappdata}
            process = subprocess.Popen(
                ["java", "-cp", str(ROOT / "out/host"),
                 "bridge.Host", str(ROOT / "out/mods"), str(port), TOKEN, "100"],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env
            )
            try:
                line = process.stdout.readline()
                if not line.startswith("INIT "):
                    self.fail(f"Unexpected host output: {line!r}")
                ready = process.stdout.readline()
                self.assertIn("READY port=", ready)
                relay = subprocess.run(
                    [str(executable)], capture_output=True, text=True,
                    timeout=15, env=env, cwd=ROOT
                )
                self.assertEqual(relay.returncode, 0, relay.stdout + relay.stderr)
                self.assertIn("RELAY_DROPPED=0", relay.stdout)
            finally:
                if process.poll() is None:
                    process.terminate()
                output, errors = process.communicate(timeout=10)
            self.assertIn("HELLO_FABRIC_JOIN", output)
            self.assertIn("HELLO_FABRIC_TICK", output)
            self.assertIn("HELLO_FABRIC_LEAVE", output)


if __name__ == "__main__":
    unittest.main()
