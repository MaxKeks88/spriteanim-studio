@echo off
rem SpriteAnim Studio: start in the background, without a console window.
rem pythonw.exe has no console and no taskbar button. For logs use run-console.bat.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
start "" pythonw server.py
exit /b 0
