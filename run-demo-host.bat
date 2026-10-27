@echo off
cd /d "%~dp0"
python tools\build.py || exit /b 1
java --limit-modules java.base -cp out\host bridge.Host out\mods 32651 dev-secret-token-0123456789 1000
