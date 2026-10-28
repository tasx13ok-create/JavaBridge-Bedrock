"""Tests for offline CurseForge modpack manifest inspection."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("modpack", ROOT / "tools" / "inspect_modpack.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CurseForgeManifestTests(unittest.TestCase):
    def test_read_manifest_without_fetching_mod_jars(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "modpack.zip"
            with ZipFile(zip_path, "w") as archive:
                archive.writestr("manifest.json", json.dumps({
                    "manifestType": "minecraftModpack", "manifestVersion": 1,
                    "minecraft": {"version": "1.21.1", "modLoaders": [
                        {"id": "fabric-0.16.9", "primary": True}
                    ]},
                    "files": [{"projectID": 1111, "fileID": 2222, "required": True}],
                    "overrides": "overrides"
                }))
            result = module.inspect_modpack(zip_path)
            self.assertEqual(result["status"], "manifest_read_only")
            self.assertEqual(result["mod_count"], 1)
            self.assertEqual(result["mod_files"][0]["file_id"], 2222)
            self.assertEqual(result["minecraft_java_version"], "1.21.1")

    def test_not_a_curseforge_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("manifest.json", '{"foo":"bar"}')
            self.assertEqual(module.inspect_modpack(path)["status"], "invalid_or_unreadable")


if __name__ == "__main__":
    unittest.main()
