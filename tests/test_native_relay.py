"""Native C++ thread + TCP -> Java host integration; simulated game events only."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "local-test-auth-token-000000000000000000000000"

class NativeRelayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["python3", str(ROOT / "tools/build.py")], check=True, capture_output=True, text=True)

    def test_cpp_worker_to_jvm(self):
        binary = ROOT / "out/transport_harness"
        subprocess.run([
            "g++", "-std=c++20", "-O0", "-pthread",
            "-I", str(ROOT / "native/levilamina-client/src"),
            str(ROOT / "native/levilamina-client/src/mod/BridgeTransport.cpp"),
            str(ROOT / "native/test/transport_harness.cpp"), "-o", str(binary)
        ], check=True, capture_output=True, text=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as home:
            cfg = Path(home) / ".config" / "CFBedrockJavaBridge" / "session.conf"
            cfg.parent.mkdir(parents=True)
            cfg.write_text(f"PORT {port}\nTOKEN {TOKEN}\n", encoding="utf8")
            cfg.chmod(0o600)
            host = subprocess.Popen([
                "java", "--limit-modules", "java.base", "-cp", str(ROOT / "out/host"),
                "bridge.Host", str(ROOT / "out/mods"), str(port), TOKEN, "100"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertIn("READY port=", next(x for x in host.stdout if "READY port=" in x))
                result = subprocess.run([str(binary)], env={**os.environ, "HOME": home},
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("RELAY_DROPPED=0", result.stdout)
                self.assertIn("LOG_RELAY=Hello from Java JAR", result.stdout)
                self.assertIn("CHAT_RELAY=JavaBridge active", result.stdout)
                host.terminate()
                output, err = host.communicate(timeout=10)
                self.assertIn("HELLO_FABRIC_JOIN", output)
                self.assertIn("HELLO_FABRIC_TICK 1", output)
                self.assertIn("HELLO_FABRIC_BREAK 10,64,-7", output)
                self.assertIn("HELLO_FABRIC_LEAVE", output)
            finally:
                if host.poll() is None:
                    host.kill()
                    host.communicate()

if __name__ == "__main__":
    unittest.main()
