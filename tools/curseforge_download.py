#!/usr/bin/env python3
"""Download a CurseForge Minecraft Java mod file through the official authenticated API.

Requires an approved CurseForge API key in CURSEFORGE_API_KEY. Files land in a
review directory and are NEVER automatically loaded into Minecraft/JavaBridge.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zipfile import is_zipfile

API_ROOT = "https://api.curseforge.com"
MAX_API_BYTES = 2 * 1024 * 1024
MAX_JAR_BYTES = 128 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected redirect; refusing to forward CurseForge credentials")


def _opener():
    return build_opener(NoRedirect())


def _url_is_cdn(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and (host == "forgecdn.net" or host.endswith(".forgecdn.net"))
            and parsed.port is None and parsed.username is None and parsed.password is None
            and not parsed.fragment and parsed.path.lower().endswith(".jar"))


def _read_api(path: str, key: str, opener) -> object:
    request = Request(API_ROOT + path, headers={"x-api-key": key, "Accept": "application/json"})
    with opener.open(request, timeout=25) as response:
        content = response.read(MAX_API_BYTES + 1)
    if len(content) > MAX_API_BYTES: raise ValueError("CurseForge API response exceeds size limit")
    response = json.loads(content)
    if not isinstance(response, dict) or "data" not in response:
        raise ValueError("Unexpected CurseForge API payload")
    return response["data"]


def _safe_name(filename: str) -> str:
    if (not filename or filename in (".", "..") or "/" in filename or "\\" in filename
            or ":" in filename or any(ord(ch) < 32 for ch in filename)
            or not filename.lower().endswith(".jar") or len(filename) > 200):
        raise ValueError("Invalid CurseForge JAR filename")
    return filename


def download_file(mod_id: int, file_id: int, key: str, output_dir: Path,
                  opener=None) -> Path:
    if mod_id < 1 or file_id < 1 or mod_id > 2_147_483_647 or file_id > 2_147_483_647:
        raise ValueError("CurseForge project and file IDs must be positive integers")
    if not key or len(key) < 8:
        raise ValueError("Approved CurseForge API key is required")
    opener = opener or _opener()
    meta = _read_api(f"/v1/mods/{mod_id}/files/{file_id}", key, opener)
    if not isinstance(meta, dict) or meta.get("id") != file_id or meta.get("modId") != mod_id:
        raise ValueError("CurseForge file metadata did not match requested IDs")
    name = _safe_name(meta.get("fileName", ""))
    declared_size = meta.get("fileLength", 0)
    if not isinstance(declared_size, int) or declared_size < 1 or declared_size > MAX_JAR_BYTES:
        raise ValueError("Invalid or oversized CurseForge file size")
    url = _read_api(f"/v1/mods/{mod_id}/files/{file_id}/download-url", key, opener)
    if not isinstance(url, str) or not _url_is_cdn(url):
        raise ValueError("Unexpected CurseForge CDN host or file URL")

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / name
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite a previously downloaded JAR: {name}")
    temp_name = None
    try:
        req = Request(url, headers={"x-api-key": key, "Accept": "application/java-archive"})
        with opener.open(req, timeout=60) as body:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".curseforge-", suffix=".part",
                                             dir=output_dir, delete=False) as temporary:
                temp_name = Path(temporary.name)
                size = 0
                sha1 = hashlib.sha1()
                sha256 = hashlib.sha256()
                while True:
                    block = body.read(64 * 1024)
                    if not block: break
                    size += len(block)
                    if size > MAX_JAR_BYTES or size > declared_size:
                        raise ValueError("Download exceeded declared CurseForge file size")
                    temporary.write(block)
                    sha1.update(block)
                    sha256.update(block)
        if size != declared_size or not is_zipfile(temp_name):
            raise ValueError("Downloaded file is incomplete or not a valid JAR ZIP")
        # CurseForge hash algorithm values: 1=SHA1, 2=MD5. Use only SHA1 as
        # a consistency check, not as a security guarantee.
        hashes = meta.get("hashes", [])
        if isinstance(hashes, list):
            for record in hashes:
                if isinstance(record, dict) and record.get("algo") == 1:
                    expected = str(record.get("value", "")).lower()
                    if len(expected) == 40 and expected != sha1.hexdigest():
                        raise ValueError("CurseForge SHA-1 checksum mismatch")
        os.replace(temp_name, destination)
        temp_name = None
        print(f"Downloaded {destination.name} ({size} bytes)")
        print("SHA-256:", sha256.hexdigest())
        print("Review this JAR before approving it to run; do NOT assume compatibility.")
        return destination
    finally:
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-id", required=True, type=int)
    parser.add_argument("--file-id", required=True, type=int)
    parser.add_argument("--dest", type=Path, default=Path("downloaded-curseforge-mods"))
    args = parser.parse_args()
    key = os.environ.get("CURSEFORGE_API_KEY", "")
    try:
        download_file(args.mod_id, args.file_id, key, args.dest)
    except Exception as error:
        parser.exit(2, "CurseForge download unavailable: " + str(error) + "\n")


if __name__ == "__main__":
    main()
