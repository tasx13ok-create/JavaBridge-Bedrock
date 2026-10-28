#!/usr/bin/env python3
"""Build Java runtime and authored demo JAR without external dependencies."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

def run(args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True)

def build():
    if not shutil.which("javac") or not shutil.which("jar"):
        raise SystemExit("JDK 21+ required (javac and jar)")
    (OUT / "host").mkdir(parents=True, exist_ok=True)
    (OUT / "demo").mkdir(parents=True, exist_ok=True)
    (OUT / "mods").mkdir(parents=True, exist_ok=True)
    sources = list((ROOT / "src").rglob("*.java"))
    run(["javac", "-encoding", "UTF-8", "-d", OUT / "host", *sources])
    run(["javac", "-encoding", "UTF-8", "-cp", OUT / "host",
         "-d", OUT / "demo", ROOT / "examples/hello-fabric/src/demo/HelloFabric.java"])
    run(["jar", "--create", "--file", OUT / "mods/hello-fabric.jar",
         "-C", OUT / "demo", ".", "-C", ROOT / "examples/hello-fabric", "fabric.mod.json"])

    # An additional JAR uses actual Fabric API package names, but is a standalone
    # fixture so it cannot alter the default smoke test's mod count.
    (OUT / "fixtures").mkdir(parents=True, exist_ok=True)
    (OUT / "fabric-tick-classes").mkdir(parents=True, exist_ok=True)
    run(["javac", "-encoding", "UTF-8", "-cp", OUT / "host",
         "-d", OUT / "fabric-tick-classes",
         ROOT / "examples/fabric-api-tick/src/demo/PlainTickMod.java"])
    run(["jar", "--create", "--file", OUT / "fixtures/fabric-api-tick.jar",
         "-C", OUT / "fabric-tick-classes", ".",
         "-C", ROOT / "examples/fabric-api-tick", "fabric.mod.json"])
    print("Built:", OUT / "mods/hello-fabric.jar",
          OUT / "fixtures/fabric-api-tick.jar")

if __name__ == "__main__":
    build()
