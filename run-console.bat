@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python server.py
if errorlevel 1 (
  echo.
  echo Startup failed: need Python 3.11+ and a running ComfyUI on port 8188.
  pause
)
