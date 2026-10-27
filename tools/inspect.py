#!/usr/bin/env python3
"""Read-only inspector for downloaded CurseForge Java mod JARs."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

def inspect_jar(path: Path) -> dict:
    report = {"filename": path.name, "loader": "unknown", "status": "unsupported"}
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if "fabric.mod.json" in names:
                report["loader"] = "fabric"
                entry = archive.getinfo("fabric.mod.json")
                if entry.file_size > 1024 * 1024:
                    raise ValueError("fabric.mod.json too large")
                metadata = json.loads(archive.read("fabric.mod.json"))
                report["mod_id"] = metadata.get("id")
                report["version"] = metadata.get("version")
                report["entrypoints"] = metadata.get("entrypoints", {})
                report["mixins"] = metadata.get("mixins", [])
                report["dependencies"] = metadata.get("depends", {})
                report["status"] = "candidate_for_experimental_host" if metadata.get("entrypoints", {}).get("main") and not metadata.get("mixins") else "requires_more_emulation"
            elif "META-INF/neoforge.mods.toml" in names:
                report["loader"] = "neoforge"
            elif "META-INF/mods.toml" in names:
                report["loader"] = "forge"
            elif "quilt.mod.json" in names:
                report["loader"] = "quilt"
            else:
                report["reason"] = "No known mod loader metadata"
    except (BadZipFile, ValueError, OSError, json.JSONDecodeError) as exc:
        report["error"] = str(exc)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="A downloaded mods folder or a single JAR")
    args = parser.parse_args()
    jars = [args.path] if args.path.is_file() else sorted(args.path.glob("*.jar"))
    print(json.dumps({"scanned": len(jars), "mods": [inspect_jar(jar) for jar in jars]}, indent=2))

if __name__ == "__main__":
    main()
