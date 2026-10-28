#!/usr/bin/env python3
"""Inspect Java .class constant pools in a JAR without executing mod bytecode.

Reports directly referenced APIs for prioritizing Java Edition compatibility.
This is a diagnostic, NOT a malware scanner or proof that a mod will work.
"""
import argparse
import json
from pathlib import Path
import struct
from zipfile import ZipFile, BadZipFile

MAX_CLASSES = 8000
MAX_CLASS_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024

def class_references(data):
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("Invalid Java class file")
    size = len(data)
    cursor = 8

    def pull(n):
        nonlocal cursor
        if cursor + n > size:
            raise ValueError("Truncated class constant pool")
        result = data[cursor:cursor + n]
        cursor += n
        return result

    count = struct.unpack(">H", pull(2))[0]
    strings = {}
    classes = []
    pos = 1
    while pos < count:
        tag = pull(1)[0]
        if tag == 1:
            n = struct.unpack(">H", pull(2))[0]
            strings[pos] = pull(n).decode("utf-8", errors="replace")
        elif tag == 7:
            classes.append(struct.unpack(">H", pull(2))[0])
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            pull(4)
        elif tag in (5, 6):
            pull(8)
            pos += 1
        elif tag in (8, 16, 19, 20):
            pull(2)
        elif tag == 15:
            pull(3)
        else:
            raise ValueError(f"Unsupported JVM constant pool tag {tag}")
        pos += 1
    return {strings[index].replace("/", ".") for index in classes if index in strings}


def analyze_jar(jar: Path) -> dict:
    report = {
        "jar": jar.name, "analyzed_classes": 0, "referenced_packages": {},
        "not_supported": [], "assessment": "unknown", "warnings": []
    }
    packages = {
        "java_minecraft": "net.minecraft.",
        "fabric_api": "net.fabricmc.fabric.api.",
        "fabric_loader": "net.fabricmc.loader.api.",
        "forge": "net.minecraftforge.",
        "neoforge": "net.neoforged.",
        "mixin": "org.spongepowered.asm.mixin.",
        "bedrock_bridge": "bridge.",
    }
    found = {key: set() for key in packages}
    total = 0
    try:
        with ZipFile(jar) as z:
            entries = [e for e in z.infolist() if e.filename.endswith(".class") and not e.is_dir()]
            if len(entries) > MAX_CLASSES:
                raise ValueError("JAR has too many class files for static analyzer")
            for entry in entries:
                if entry.file_size > MAX_CLASS_BYTES:
                    report["warnings"].append(f"Skipped oversized class: {entry.filename}")
                    continue
                total += entry.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Class data limit exceeded")
                try:
                    with z.open(entry) as inp:
                        data = inp.read(MAX_CLASS_BYTES + 1)
                    if len(data) > MAX_CLASS_BYTES:
                        continue
                    refs = class_references(data)
                    report["analyzed_classes"] += 1
                    for ref in refs:
                        for group, prefix in packages.items():
                            if ref.startswith(prefix):
                                found[group].add(ref)
                except (ValueError, OSError, RuntimeError) as exc:
                    report["warnings"].append(f"{entry.filename}: {exc}")
    except (BadZipFile, OSError, ValueError) as exc:
        report["warnings"].append(str(exc))
        report["assessment"] = "inspection_failed"
        return report

    report["referenced_packages"] = {
        group: {"count": len(refs), "examples": sorted(refs)[:12]}
        for group, refs in found.items() if refs
    }
    unsupported = [group for group in ("java_minecraft", "forge", "neoforge", "mixin") if found[group]]
    report["not_supported"] = unsupported
    if unsupported:
        report["assessment"] = "requires_unimplemented_game_apis"
    elif found["fabric_api"] or found["fabric_loader"]:
        report["assessment"] = "requires_individual_api_compatibility_check"
    else:
        report["assessment"] = "no_known_unsupported_api_reference_detected"
    report["warnings"].append(
        "Static references cannot detect reflection, invokedynamic linkage, native libraries, or runtime behavior."
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Downloaded JAR or directory of JARs")
    args = parser.parse_args()
    files = [args.path] if args.path.is_file() else sorted(args.path.glob("*.jar"))
    print(json.dumps({"jars": [analyze_jar(f) for f in files]}, indent=2))


if __name__ == "__main__":
    main()
