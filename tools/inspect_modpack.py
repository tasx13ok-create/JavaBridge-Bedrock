#!/usr/bin/env python3
"""Read CurseForge Minecraft Java modpack manifests without downloading or running mods."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile


def inspect_modpack(path: Path) -> dict:
    report = {"filename": path.name, "format": "unknown", "status": "unsupported"}
    try:
        with ZipFile(path) as archive:
            entry = archive.getinfo("manifest.json")
            if entry.file_size > 1024 * 1024:
                raise ValueError("CurseForge manifest.json exceeds 1 MiB")
            raw = archive.read("manifest.json")
            if len(raw) > 1024 * 1024:
                raise ValueError("Manifest decompressed too large")
            manifest = json.loads(raw)
            if not isinstance(manifest, dict) or manifest.get("manifestType") != "minecraftModpack":
                raise ValueError("Not a CurseForge Minecraft modpack manifest")
            report["format"] = "curseforge_minecraft_modpack"
            minecraft = manifest.get("minecraft", {})
            if not isinstance(minecraft, dict):
                raise ValueError("Invalid minecraft field")
            report["minecraft_java_version"] = minecraft.get("version")
            report["modloaders"] = minecraft.get("modLoaders", [])
            files = manifest.get("files", [])
            if not isinstance(files, list) or len(files) > 10000:
                raise ValueError("Invalid or oversized modpack file list")
            mods = []
            for file in files:
                if not isinstance(file, dict): raise ValueError("Invalid file record")
                project_id, file_id = file.get("projectID"), file.get("fileID")
                if not isinstance(project_id, int) or not isinstance(file_id, int) or project_id < 1 or file_id < 1:
                    raise ValueError("Invalid CurseForge project or file ID")
                mods.append({
                    "project_id": project_id,
                    "file_id": file_id,
                    "required": file.get("required", True),
                })
            report["mod_files"] = mods
            report["mod_count"] = len(mods)
            report["overrides_folder"] = manifest.get("overrides", "overrides")
            report["status"] = "manifest_read_only"
            report["notice"] = (
                "Manifest IDs identify CurseForge downloads, not JavaBridge-compatible mods. "
                "This tool downloads, installs, and executes nothing."
            )
    except (BadZipFile, KeyError, OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        report["status"] = "invalid_or_unreadable"
        report["error"] = str(error)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modpack", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect_modpack(args.modpack)
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
