"""End-to-end tests of direct-JAR demo execution and simulated event relays."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "local-development-token-123456789"

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    def start_host(self):
        port = free_port()
        proc = subprocess.Popen([
            "java", "-cp", str(ROOT / "out/host"), "bridge.Host",
            str(ROOT / "out/mods"), str(port), TOKEN, "100"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(100):
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                return proc, connection, port
            except OSError:
                if proc.poll() is not None:
                    out, err = proc.communicate()
                    self.fail("Host failed: " + out + " " + err)
                time.sleep(0.05)
        proc.kill()
        self.fail("Host did not listen")

    def test_direct_jar_entrypoint_and_ticks(self):
        proc, connection, _ = self.start_host()
        with connection, connection.makefile("rw", buffering=1) as wire:
            wire.write("HELLO " + TOKEN + "\n")
            self.assertEqual(wire.readline().strip(), "OK bridge-v0")
            wire.write("STATUS\n")
            self.assertEqual(wire.readline().strip(), "STATUS loaded=1 skipped=0 handlers=1")
            for _ in range(3):
                wire.write("TICK\n")
                self.assertEqual(wire.readline().strip(), "TICK_OK handlers=1")
            wire.write("STOP\n")
            self.assertEqual(wire.readline().strip(), "BYE")
        out, err = proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn("HELLO_FABRIC_INIT direct Java bytecode executed", out)
        self.assertIn("HELLO_FABRIC_TICK 3", out)

    def test_bad_auth_rejected(self):
        proc, connection, _ = self.start_host()
        with connection, connection.makefile("rw", buffering=1) as wire:
            wire.write("HELLO wrong-token\n")
            self.assertEqual(wire.readline().strip(), "ERROR unauthorized")
        proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0)

    def test_inspect_demo(self):
        out = subprocess.check_output([
            sys.executable, str(ROOT / "tools/inspect.py"), str(ROOT / "out/mods")
        ], text=True)
        report = json.loads(out)
        self.assertEqual(report["scanned"], 1)
        self.assertEqual(report["mods"][0]["loader"], "fabric")
        self.assertEqual(report["mods"][0]["mod_id"], "hello_fabric_bridge")

    def test_native_simulator_source_builds(self):
        subprocess.run([
            "g++", "-std=c++20", "-O2", "-Wall", "-Wextra",
            str(ROOT / "native/adapter_sim.cpp"), "-o", str(ROOT / "out/adapter_sim")
        ], check=True, capture_output=True, text=True)

if __name__ == "__main__":
    unittest.main()
