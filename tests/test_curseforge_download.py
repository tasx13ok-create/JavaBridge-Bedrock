"""Offline mocked tests for official CurseForge API downloads (no network/key needed)."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import Request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("curseforge", ROOT / "tools" / "curseforge_download.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_jar():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("fabric.mod.json", '{"id":"mock","entrypoints":{"main":["a.Mod"]}}')
    return buffer.getvalue()


class FakeResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class FakeOpener:
    def __init__(self, archive, filename="test.jar", url="https://edge.forgecdn.net/files/1/2/test.jar"):
        self.archive = archive
        self.filename = filename
        self.url = url
        self.requests = []
    def open(self, request: Request, timeout=25):
        self.requests.append(request)
        address = request.full_url
        if address.endswith("/download-url"):
            return FakeResponse(json.dumps({"data": self.url}).encode())
        if address.startswith("https://api.curseforge.com"):
            data = {"id": 456, "modId": 123, "fileName": self.filename,
                    "fileLength": len(self.archive), "hashes": [
                        {"algo": 1, "value": hashlib.sha1(self.archive).hexdigest()}
                    ]}
            return FakeResponse(json.dumps({"data": data}).encode())
        return FakeResponse(self.archive)


class CurseForgeDownloadTests(unittest.TestCase):
    def test_authenticated_download_saves_jar_without_execution(self):
        opener = FakeOpener(fake_jar())
        with tempfile.TemporaryDirectory() as path:
            destination = module.download_file(123, 456, "TESTKEY123", Path(path), opener)
            self.assertEqual(destination.read_bytes(), opener.archive)
            self.assertEqual(destination.name, "test.jar")
            self.assertEqual(len(opener.requests), 3)
            self.assertTrue(all(req.get_header("X-api-key") == "TESTKEY123" for req in opener.requests))
            self.assertFalse((Path(path) / "approved-mods.tsv").exists())

    def test_untrusted_cdn_url_rejected(self):
        opener = FakeOpener(fake_jar(), url="https://unsafe.example.com/steal.jar")
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(ValueError, "CDN host"):
                module.download_file(123, 456, "TESTKEY123", Path(path), opener)
            self.assertEqual(len(list(Path(path).glob("*.jar"))), 0)

    def test_unsafe_filename_rejected(self):
        opener = FakeOpener(fake_jar(), filename="../../bad.jar")
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(ValueError, "filename"):
                module.download_file(123, 456, "TESTKEY123", Path(path), opener)

    def test_no_key_no_download(self):
        opener = FakeOpener(fake_jar())
        with self.assertRaisesRegex(ValueError, "API key"):
            module.download_file(123, 456, "", Path("unused"), opener)
        self.assertEqual(len(opener.requests), 0)


if __name__ == "__main__": unittest.main()
