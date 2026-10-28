#!/usr/bin/env python3
"""Run local authenticated Java host for a separate LeviLamina client plugin."""
import argparse
import os
from queue import Queue, Empty
import time
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
STARTUP_TIMEOUT_SECONDS = 45


def _read_lines(pipe, queue: Queue) -> None:
    try:
        for line in pipe:
            queue.put(line)
    finally:
        queue.put(None)


def wait_for_ready(process, queue: Queue, seconds: float = STARTUP_TIMEOUT_SECONDS) -> None:
    """Fail with a bounded deadline if approved Java bytecode hangs during init."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            line = queue.get(timeout=min(0.3, max(0.001, deadline - time.monotonic())))
        except Empty:
            if process.poll() is not None:
                raise RuntimeError("Java host exited before READY")
            continue
        if line is None:
            raise RuntimeError("Java host closed stdout before READY")
        print(line, end="", flush=True)
        if line.startswith("READY port="):
            return
    raise TimeoutError("Java host did not become READY before the startup deadline")


def forward_logs(process, queue: Queue) -> int:
    """Transfer JVM logs without blocking indefinitely after process exit."""
    while True:
        try:
            line = queue.get(timeout=0.3)
        except Empty:
            if process.poll() is not None:
                return process.wait()
            continue
        if line is None:
            return process.wait()
        print(line, end="", flush=True)



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
        str(trusted), "--reconnect"
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1)
    log_queue: Queue = Queue()
    threading.Thread(target=_read_lines, args=(proc.stdout, log_queue), daemon=True).start()
    try:
        try:
            wait_for_ready(proc, log_queue)
        except (RuntimeError, TimeoutError) as problem:
            print("JavaBridge startup failed: " + str(problem), file=sys.stderr)
            return 1
        cfgpath.parent.mkdir(parents=True, exist_ok=True)
        cfgpath.write_text(f"PORT {port}\nTOKEN {token}\n", encoding="utf-8")
        if os.name != "nt": cfgpath.chmod(0o600)
        print("JavaBridge session ready; now start isolated Bedrock test instance.", flush=True)
        return forward_logs(proc, log_queue)
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
