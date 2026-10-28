"""Tests for the conservative, offline mod JAR compatibility inspector."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inspect_jar_tool", ROOT / "tools" / "inspect.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectorTests(unittest.TestCase):
    def test_synthetic_jar_with_minecraft_calls_is_not_claimed_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            jar = Path(tmp) / "example.jar"
            with ZipFile(jar, "w") as archive:
                archive.writestr("fabric.mod.json", json.dumps({
                    "id": "synthetic", "version": "1.0", "entrypoints": {"main": ["a.Main"]}
                }))
                archive.writestr("a/Main.class", b"\xca\xfe\xba\xbe|net/minecraft/server/MinecraftServer|")
            report = module.inspect_jar(jar)
            self.assertEqual(report["loader"], "fabric")
            self.assertIn("java_edition_internals", report["risk_flags"])
            self.assertEqual(report["status"], "requires_unimplemented_java_edition_apis")
            self.assertEqual(len(report["sha256"]), 64)

    def test_mixin_config_blocks_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            jar = Path(tmp) / "mod.jar"
            with ZipFile(jar, "w") as archive:
                archive.writestr("fabric.mod.json", json.dumps({
                    "id": "mixin_mod", "mixins": ["foo.mixins.json"],
                    "entrypoints": {"main": ["test.Mod"]}
                }))
            report = module.inspect_jar(jar)
            self.assertIn("mixin_configuration", report["risk_flags"])
            self.assertEqual(report["status"], "requires_unimplemented_java_edition_apis")

    def test_unsupported_loaders(self):
        for filename, loader in [("META-INF/mods.toml", "forge"),
                                 ("META-INF/neoforge.mods.toml", "neoforge"),
                                 ("quilt.mod.json", "quilt")]:
            with self.subTest(loader=loader), tempfile.TemporaryDirectory() as tmp:
                jar = Path(tmp) / "mod.jar"
                with ZipFile(jar, "w") as archive:
                    archive.writestr(filename, "test")
                report = module.inspect_jar(jar)
                self.assertEqual(report["loader"], loader)
                self.assertEqual(report["status"], "loader_not_implemented")

    def test_invalid_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            jar = Path(tmp) / "bad.jar"
            jar.write_bytes(b"not a zip")
            self.assertEqual(module.inspect_jar(jar)["status"], "invalid_or_unreadable_jar")

    def test_scan_does_not_decompress_oversized_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            jar = Path(tmp) / "big.jar"
            with ZipFile(jar, "w") as archive:
                archive.writestr("fabric.mod.json", '{"entrypoints":{"main":["test.Mod"]},"id":"big"}')
                archive.writestr("Large.class", b"x" * (module.CLASS_LIMIT + 1))
            report = module.inspect_jar(jar)
            self.assertTrue(report["class_scan_truncated"])
            self.assertEqual(report["status"], "requires_unimplemented_java_edition_apis")


if __name__ == "__main__":
    unittest.main()
