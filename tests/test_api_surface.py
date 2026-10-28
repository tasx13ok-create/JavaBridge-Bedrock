"""Verify Java class-file reference scanning never executes a downloaded JAR."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("api_surface", ROOT / "tools/api_surface.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ApiSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")],
                       check=True, capture_output=True, text=True)

    def test_authored_demo_class_references(self):
        report = MODULE.analyze_jar(ROOT / "out/mods/hello-fabric.jar")
        self.assertGreater(report["analyzed_classes"], 0)
        self.assertEqual(report["assessment"], "no_known_unsupported_api_reference_detected")
        self.assertIn("bedrock_bridge", report["referenced_packages"])

    def test_fabric_api_fixture_is_reported_without_execution(self):
        report = MODULE.analyze_jar(ROOT / "out/fixtures/fabric-api-tick.jar")
        self.assertEqual(report["assessment"], "requires_individual_api_compatibility_check")
        self.assertIn("fabric_api", report["referenced_packages"])

    def test_corrupt_class_handled_without_crash(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / "malformed.jar"
            with ZipFile(jar, "w") as archive:
                archive.writestr("invalid.class", b"bad")
            report = MODULE.analyze_jar(jar)
        self.assertEqual(report["analyzed_classes"], 0)
        self.assertTrue(any("Invalid Java class" in s for s in report["warnings"]))

    def test_handmade_minecraft_reference_is_classified(self):
        import struct
        target = b"net/minecraft/world/level/Level"
        # Class header; cp_count=3; #1 UTF8; #2 CONSTANT_Class -> #1.
        raw = (b"\xca\xfe\xba\xbe" + struct.pack(">HH", 0, 61) +
               struct.pack(">H", 3) + b"\x01" + struct.pack(">H", len(target)) +
               target + b"\x07\x00\x01")
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / "java-game.jar"
            with ZipFile(jar, "w") as archive:
                archive.writestr("test.class", raw)
            report = MODULE.analyze_jar(jar)
        self.assertIn("java_minecraft", report["not_supported"])


if __name__ == "__main__":
    unittest.main()
