#!/usr/bin/env python3
"""Run local authenticated Java host for a separate LeviLamina client plugin."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]

def session_path() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise RuntimeError("LOCALAPPDATA not set")
        return Path(root) / "CFBedrockJavaBridge" / "session.conf"
    return Path.home() / ".config" / "CFBedrockJavaBridge" / "session.conf"

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mods", type=Path, default=ROOT / "out/mods")
    ap.add_argument("--max-events", type=int, default=200000)
    ap.add_argument("--trust-file", type=Path, help="Hash allowlist (default: <mods>/approved-mods.tsv)")
    args = ap.parse_args()
    if not (ROOT / "out/host/bridge/Host.class").exists():
        print("Run python tools/build.py first", file=sys.stderr)
        return 2
    if not args.mods.is_dir() or not 1 <= args.max_events <= 1000000:
        print("Invalid mods folder or max-events", file=sys.stderr)
        return 2
    trusted = args.trust_file or args.mods / "approved-mods.tsv"
    if not trusted.is_file():
        print("Refusing to start unapproved Java mods. Review all JARs then run:", file=sys.stderr)
        print(f"  python tools/approve_mods.py --mods \"{args.mods}\" --yes", file=sys.stderr)
        return 2
    cfgpath = session_path()
    if cfgpath.exists():
        print("Existing session found; refusing to overwrite", file=sys.stderr)
        return 2
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    token = secrets.token_hex(32)
    proc = subprocess.Popen([
        "java", "--limit-modules", "java.base", "-cp", str(ROOT / "out/host"),
        "bridge.Host", str(args.mods), str(port), token, str(args.max_events),
        str(trusted)
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1)
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                print("Host terminated before READY", file=sys.stderr)
                return proc.wait() or 1
            print(line, end="", flush=True)
            if line.startswith("READY port="):
                break
        cfgpath.parent.mkdir(parents=True, exist_ok=True)
        cfgpath.write_text(f"PORT {port}\nTOKEN {token}\n", encoding="utf-8")
        if os.name != "nt": cfgpath.chmod(0o600)
        print("JavaBridge session ready; now start isolated Bedrock test instance.", flush=True)
        thread = threading.Thread(target=lambda: [print(line, end="", flush=True) for line in proc.stdout], daemon=True)
        thread.start()
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return 130
    finally:
        if cfgpath.is_file():
            try:
                if cfgpath.read_text(encoding="utf-8") == f"PORT {port}\nTOKEN {token}\n":
                    cfgpath.unlink()
            except OSError: pass
        if proc.poll() is None:
            proc.terminate()
            proc.wait()

if __name__ == "__main__":
    sys.exit(main())
