#!/usr/bin/env python3
"""Build a reproducible JavaBridge sidecar source/runtime ZIP (NOT a Bedrock DLL)."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "JavaBridge-Runtime-v0.3"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)

DIRECT_FILES = [
    "README.md", "LICENSE", "RELEASE_NOTES.md",
    "run-demo-host.bat", "run-demo-adapter.bat", "run-demo-host.sh",
    "run-client-bridge.bat", "tools/build.py", "tools/start_client_bridge.py",
    "tools/adapter_sim.py", "tools/inspect.py"
]
GLOBS = [
    "src/**/*.java",
    "examples/**/*.java",
    "examples/**/fabric.mod.json",
    "out/host/**/*.class",
    "out/mods/*.jar",
    "out/fixtures/*.jar",
]


def included() -> list[Path]:
    files = {ROOT / name for name in DIRECT_FILES}
    for pattern in GLOBS:
        files.update(ROOT.glob(pattern))
    return sorted(path for path in files if path.is_file())


def package(output: Path) -> int:
    if not (ROOT / "out/host/bridge/Host.class").is_file():
        raise SystemExit("Build Java runtime first: python tools/build.py")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = included()
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            relative = file.relative_to(ROOT).as_posix()
            if "session.conf" in relative or relative.startswith("out/log"):
                raise ValueError("Refusing to include session secrets or logs")
            entry = ZipInfo(PREFIX + "/" + relative, date_time=FIXED_TIME)
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, file.read_bytes(), compress_type=ZIP_DEFLATED,
                             compresslevel=9)
    print(f"Packaged {len(files)} files into {output}")
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "out/JavaBridge-Runtime-v0.3.zip")
    args = parser.parse_args()
    package(args.output)


if __name__ == "__main__":
    main()
