@echo off
cd /d "%~dp0"
python -m tools.gui_manager
if errorlevel 1 pause
