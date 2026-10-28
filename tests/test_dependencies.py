"""Exercise dependency ordering, missing IDs, and dependency cycles."""
from pathlib import Path
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "dependency-graph-token-123456789"


class DependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    @staticmethod
    def make_jar(folder, name, mod_id, dependencies=None, initializer=True):
        """Use JDK tools to build an actual .jar with Java bytecode."""
        cls = "Mod_" + mod_id.replace("-", "_")
        directory = folder / cls
        directory.mkdir()
        if initializer:
            source = directory / (cls + ".java")
            source.write_text(f"""
                package fixture;
                import net.fabricmc.api.ModInitializer;
                import net.fabricmc.loader.api.FabricLoader;
                public final class {cls} implements ModInitializer {{
                    public void onInitialize() {{
                        System.out.println("DEPENDENCY_INIT {mod_id} priorBase=" +
                            FabricLoader.getInstance().isModLoaded("base"));
                    }}
                }}
            """, encoding="utf-8")
            subprocess.run(["javac", "-cp", str(ROOT / "out/host"),
                            "-d", str(directory), str(source)],
                           check=True, capture_output=True)
        jar = folder / name
        meta = {"id": mod_id, "version": "1.0",
                "entrypoints": {"main": ["fixture." + cls]},
                "depends": dependencies or {"java": ">=21"}}
        with ZipFile(jar, "w", ZIP_DEFLATED) as archive:
            archive.writestr("fabric.mod.json", json.dumps(meta))
            for file in directory.rglob("*.class"):
                archive.write(file, file.relative_to(directory))
        return jar

    def exercise(self, folder):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        p = subprocess.Popen(["java", "-cp", str(ROOT / "out/host"),
                              "bridge.Host", str(folder), str(port), TOKEN, "5"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            connection = None
            for _ in range(80):
                try:
                    connection = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                    break
                except OSError:
                    if p.poll() is not None: break
                    time.sleep(0.05)
            self.assertIsNotNone(connection, "host failed to listen")
            with connection, connection.makefile("rw", buffering=1) as wire:
                wire.write("HELLO " + TOKEN + "\n")
                self.assertEqual(wire.readline().strip(), "OK bridge-v0")
                wire.write("STATUS\n")
                status = wire.readline().strip()
                wire.write("STOP\n")
                self.assertEqual(wire.readline().strip(), "BYE")
            output, errors = p.communicate(timeout=10)
            self.assertEqual(p.returncode, 0, errors)
            return status, output, errors
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()

    def test_orders_dependencies_not_jar_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_jar(folder, "AA-dependent.jar", "dependent", {"base": "*"})
            self.make_jar(folder, "ZZ-base.jar", "base")
            status, out, err = self.exercise(folder)
            self.assertIn("loaded=2 skipped=0", status)
            self.assertLess(out.index("INIT base"), out.index("INIT dependent"))
            self.assertIn("DEPENDENCY_INIT dependent priorBase=true", out)

    def test_missing_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_jar(folder, "missing.jar", "missing", {"unavailable_library": "*"})
            status, out, err = self.exercise(folder)
            self.assertIn("loaded=0 skipped=1", status)
            self.assertIn("unsatisfied dependency: unavailable_library", err)

    def test_cycle_does_not_execute_any_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_jar(folder, "a.jar", "alpha", {"beta": "*"})
            self.make_jar(folder, "b.jar", "beta", {"alpha": "*"})
            status, out, err = self.exercise(folder)
            self.assertIn("loaded=0 skipped=2", status)
            self.assertIn("cyclic dependencies", err)
            self.assertNotIn("DEPENDENCY_INIT", out)


if __name__ == "__main__":
    unittest.main()
