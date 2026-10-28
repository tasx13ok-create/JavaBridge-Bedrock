"""Compile and execute a standalone mod using a declared Fabric nested JAR dependency."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "nested-test-token-00000000000000000"

class NestedJarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    def test_nested_jar_binary_resolves(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lib = root / "lib"
            lib.mkdir()
            (lib / "Library.java").write_text(
                'package nested; public class Library { public static String value(){ return "loaded"; } }',
                encoding="utf-8")
            classes = root / "libclasses"
            classes.mkdir()
            subprocess.run(["javac", "-d", str(classes), str(lib / "Library.java")], check=True, capture_output=True)
            library = root / "library.jar"
            subprocess.run(["jar", "--create", "--file", str(library), "-C", str(classes), "."],
                           check=True, capture_output=True)
            source = root / "UsesLibrary.java"
            source.write_text(
                'package nested; import net.fabricmc.api.ModInitializer; ' +
                'public class UsesLibrary implements ModInitializer { public void onInitialize() { ' +
                'System.out.println("NESTED_RESULT=" + Library.value()); } }', encoding="utf-8")
            modclasses = root / "modclasses"
            modclasses.mkdir()
            cp = str(ROOT / "out/host") + os.pathsep + str(library)
            subprocess.run(["javac", "-cp", cp, "-d", str(modclasses), str(source)],
                           check=True, capture_output=True)
            mods = root / "mods"
            mods.mkdir()
            with ZipFile(mods / "embedded.jar", "w", ZIP_DEFLATED) as archive:
                archive.writestr("fabric.mod.json", json.dumps({
                    "id": "embedded", "entrypoints": {"main": ["nested.UsesLibrary"]},
                    "jars": [{"file": "META-INF/jars/library.jar"}]
                }))
                for file in modclasses.rglob("*.class"):
                    archive.write(file, file.relative_to(modclasses))
                archive.write(library, "META-INF/jars/library.jar")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            host = subprocess.Popen(["java", "-cp", str(ROOT / "out/host"),
                                     "bridge.Host", str(mods), str(port), TOKEN, "10"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                conn = None
                for _ in range(80):
                    try:
                        conn = socket.create_connection(("127.0.0.1", port), timeout=.4)
                        break
                    except OSError:
                        time.sleep(.05)
                self.assertIsNotNone(conn)
                with conn, conn.makefile("rw", buffering=1) as wire:
                    wire.write("HELLO " + TOKEN + "\n")
                    self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                    wire.write("STATUS\n")
                    self.assertIn("loaded=1 skipped=0", wire.readline())
                    wire.write("STOP\n")
                    self.assertEqual(wire.readline().strip(), "BYE")
                out, err = host.communicate(timeout=10)
                self.assertEqual(host.returncode, 0, err)
                self.assertIn("NESTED_RESULT=loaded", out)
                self.assertIn("NESTED_JAR embedded.jar", out)
            finally:
                if host.poll() is None:
                    host.kill()
                    host.communicate()

if __name__ == "__main__":
    unittest.main()
