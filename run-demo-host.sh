#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 tools/build.py
java --limit-modules java.base -cp out/host bridge.Host out/mods 32651 dev-secret-token-0123456789 1000
