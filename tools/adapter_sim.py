#!/usr/bin/env python3
"""Standalone fake game events for development; NOT Minecraft Bedrock."""
import socket
import sys

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 32651
    token = sys.argv[2] if len(sys.argv) > 2 else "dev-secret-token-0123456789"
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
            with connection.makefile("rw", encoding="utf-8", buffering=1) as session:
                for command in [f"HELLO {token}", "STATUS", "TICK", "TICK", "TICK", "STOP"]:
                    session.write(command + "\n")
                    print("<", session.readline().strip())
    except OSError as exc:
        print(f"Cannot connect to JVM host: {exc}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
