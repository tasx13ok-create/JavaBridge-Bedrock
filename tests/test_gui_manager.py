"""GUI helper tests run without creating a Tk window."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.gui_manager import stage_jar, approve_jar, safe_name


class ModManagerTests(unittest.TestCase):
    def test_staging_does_not_approve(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            source = directory / "mod.jar"
            with ZipFile(source, "w") as archive:
                archive.writestr("fabric.mod.json", '{"id":"demo"}')
            staging = directory / "staging"
            mods = directory / "mods"
            staged = stage_jar(source, staging)
            self.assertEqual(staged.read_bytes(), source.read_bytes())
            self.assertFalse((mods / "approved-mods.tsv").exists())
            target = approve_jar(staged, mods)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(),
                          (mods / "approved-mods.tsv").read_text(encoding="utf-8"))

    def test_duplicate_staging_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "test.jar"
            with ZipFile(p, "w") as archive:
                archive.writestr("fabric.mod.json", '{"id":"demo"}')
            stage_jar(p, Path(folder) / "staging")
            with self.assertRaises(FileExistsError):
                stage_jar(p, Path(folder) / "staging")

    def test_bad_names_rejected(self):
        for name in ("../../evil.jar", "bad\\name.jar", "mod.zip", "oops.jar\n",
                     "path/to.jar"):
            self.assertFalse(safe_name(name))


if __name__ == "__main__":
    unittest.main()
