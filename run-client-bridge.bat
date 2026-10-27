@echo off
cd /d "%~dp0"
python tools\build.py || exit /b 1
python tools\start_client_bridge.py --mods out\mods
pause
