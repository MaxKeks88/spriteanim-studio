"""Запуск SpriteAnim Studio как отдельного приложения.

Поднимает сервер в фоне и открывает окно без адресной строки (Edge/Chrome
в режиме --app со своим профилем рядом с программой). Закрыли окно — вышли.
Если Edge не найден, открывается обычный браузер (страница живёт, пока сервер).

Собранная версия (PyInstaller) вызывает этот же файл.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("SPRITE_NO_BROWSER", "1")

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# В windowed-сборке stdout/stderr нет: пишем лог рядом с программой.
if sys.stdout is None or sys.stderr is None or getattr(sys, "frozen", False):
    _base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else HERE
    try:
        _dir = _base / ".cache"
        _dir.mkdir(parents=True, exist_ok=True)
        _fh = (_dir / "studio.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = _fh
        sys.stderr = _fh
    except OSError:
        pass

import server  # noqa: E402

URL = f"http://{server.HOST}:{server.PORT}"


def wait_port(timeout: float = 25.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", server.PORT), 0.3):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def find_browser() -> str | None:
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
             os.environ.get("LOCALAPPDATA")]
    for relative in ("Microsoft\\Edge\\Application\\msedge.exe",
                     "Google\\Chrome\\Application\\chrome.exe"):
        for root in roots:
            if not root:
                continue
            exe = Path(root) / relative
            if exe.is_file():
                return str(exe)
    return None


def main() -> None:
    threading.Thread(target=server.serve, daemon=True).start()
    if not wait_port():
        print("сервер не поднялся")
        return
    browser = find_browser()
    if not browser:
        import webbrowser
        webbrowser.open(URL)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        server.shutdown_app()
        return
    profile = server.ROOT / ".profile"
    args = [browser, f"--app={URL}", f"--user-data-dir={profile}",
            "--window-size=1500,950", "--no-first-run", "--no-default-browser-check",
            "--disable-features=Translate"]
    proc = subprocess.Popen(args)
    proc.wait()
    server.shutdown_app()


if __name__ == "__main__":
    main()
