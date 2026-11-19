@echo off
rem SpriteAnim Studio: настольное окно (pywebview), без консоли.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
start "" pythonw desktop\main.py
exit /b 0
