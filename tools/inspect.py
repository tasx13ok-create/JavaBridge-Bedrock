#!/usr/bin/env python3
"""Conservative read-only compatibility analysis for downloaded Java Edition .jar mods.

No JAR bytecode is executed. A 'candidate' is not proof that a mod will run.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

METADATA_LIMIT = 1024 * 1024
CLASS_LIMIT = 512 * 1024
BYTE_BUDGET = 16 * 1024 * 1024
CLASS_BUDGET = 2048
MARKERS = {
    "java_edition_internals": b"net/minecraft/",
    "fabric_api": b"net/fabricmc/fabric/api/",
    "mixin_bytecode": b"org/spongepowered/asm/mixin/",
    "forge_api": b"net/minecraftforge/",
    "neoforge_api": b"net/neoforged/",
    "opengl_lwjgl": b"org/lwjgl/",
}
BLOCKING_FLAGS = frozenset(MARKERS)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(128 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def _symbols(archive: ZipFile) -> tuple[list[str], bool]:
    """Heuristic byte search, NOT a verifier or full Java constant-pool parser."""
    found: set[str] = set()
    scanned_bytes = 0
    scanned_classes = 0
    truncated = False
    for info in archive.infolist():
        if not info.filename.endswith(".class"):
            continue
        if scanned_classes >= CLASS_BUDGET or scanned_bytes + info.file_size > BYTE_BUDGET:
            truncated = True
            break
        if info.file_size > CLASS_LIMIT:
            truncated = True
            continue
        scanned_bytes += info.file_size
        scanned_classes += 1
        data = archive.read(info)
        for name, marker in MARKERS.items():
            if marker in data:
                found.add(name)
        if len(found) == len(MARKERS):
            break
    return sorted(found), truncated


def inspect_jar(path: Path) -> dict:
    report: dict = {
        "filename": path.name,
        "loader": "unknown",
        "status": "unsupported",
        "analysis_method": "metadata_plus_conservative_bytecode_markers",
    }
    try:
        report["size_bytes"] = path.stat().st_size
        report["sha256"] = _digest(path)
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            flags, truncated = _symbols(archive)
            report["risk_flags"] = flags
            report["class_scan_truncated"] = truncated
            if "fabric.mod.json" in names:
                report["loader"] = "fabric"
                entry = archive.getinfo("fabric.mod.json")
                if entry.file_size > METADATA_LIMIT:
                    raise ValueError("fabric.mod.json too large")
                metadata = json.loads(archive.read("fabric.mod.json"))
                if not isinstance(metadata, dict):
                    raise ValueError("fabric.mod.json root must be an object")
                report["mod_id"] = metadata.get("id")
                report["version"] = metadata.get("version")
                report["entrypoints"] = metadata.get("entrypoints", {})
                report["mixins"] = metadata.get("mixins", [])
                report["dependencies"] = metadata.get("depends", {})
                if metadata.get("mixins"):
                    report["risk_flags"] = sorted(set(flags) | {"mixin_configuration"})
                if (not isinstance(metadata.get("entrypoints"), dict) or
                        not (metadata["entrypoints"].get("main") or metadata["entrypoints"].get("client"))):
                    report["status"] = "no_supported_fabric_entrypoint"
                elif report["risk_flags"] or truncated:
                    report["status"] = "requires_unimplemented_java_edition_apis"
                else:
                    report["status"] = "experimental_host_candidate_unverified"
            elif "META-INF/neoforge.mods.toml" in names:
                report["loader"] = "neoforge"
                report["status"] = "loader_not_implemented"
            elif "META-INF/mods.toml" in names:
                report["loader"] = "forge"
                report["status"] = "loader_not_implemented"
            elif "quilt.mod.json" in names:
                report["loader"] = "quilt"
                report["status"] = "loader_not_implemented"
            else:
                report["reason"] = "No recognized mod loader metadata"
    except (BadZipFile, ValueError, OSError, json.JSONDecodeError, RuntimeError) as exc:
        report["status"] = "invalid_or_unreadable_jar"
        report["error"] = str(exc)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Downloaded mods directory or a single .jar")
    parser.add_argument("--output", type=Path, help="Write JSON report to a specified file")
    args = parser.parse_args()
    if not args.path.exists():
        parser.error(f"Path does not exist: {args.path}")
    jars = [args.path] if args.path.is_file() else sorted(args.path.glob("*.jar"))
    report = {
        "scanned": len(jars),
        "disclaimer": "This analysis cannot establish Java Edition mod compatibility with Minecraft Bedrock.",
        "mods": [inspect_jar(jar) for jar in jars],
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
