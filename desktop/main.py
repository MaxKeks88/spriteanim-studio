"""SpriteAnim Studio — настольное окно приложения.

Поднимает ``server.py`` в фоне и показывает интерфейс в отдельном окне
(pywebview + Microsoft Edge WebView2). Браузер, адресная строка и вкладки
не используются; закрыли окно — приложение завершилось.

Запуск из проекта:   python desktop/main.py
Сборка:              python desktop/build.py
Диагностика:         SPRITE_DEBUG=1  — DevTools и контекстное меню
                     SPRITE_SMOKE=1  — скрытое окно, самозакрытие (проверка сборки)
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("SPRITE_NO_BROWSER", "1")

FROZEN = bool(getattr(sys, "frozen", False))
HERE = Path(__file__).resolve().parent
PROJECT = Path(sys.executable).resolve().parent if FROZEN else HERE.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

# В windowed-сборке stdout/stderr отсутствуют — пишем лог рядом с программой.
BASE = PROJECT
CACHE = BASE / ".cache"
if sys.stdout is None or sys.stderr is None or FROZEN:
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        log = CACHE / "studio.log"
        if log.is_file() and log.stat().st_size > 1_000_000:
            log.replace(CACHE / "studio.log.1")
        handle = log.open("a", encoding="utf-8", buffering=1)
        sys.stdout = handle
        sys.stderr = handle
    except OSError:
        pass

import server  # noqa: E402

URL = f"http://{server.HOST}:{server.PORT}"
TITLE = "SpriteAnim Studio"
SMOKE = os.environ.get("SPRITE_SMOKE") == "1"
DEBUG = os.environ.get("SPRITE_DEBUG") == "1"

if FROZEN:
    ICON = Path(getattr(sys, "_MEIPASS", BASE)) / "desktop" / "icon.ico"
else:
    ICON = HERE / "icon.ico"

SPLASH = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>SpriteAnim Studio</title>
<style>
  html,body{margin:0;height:100%;background:#0e1014;color:#e8ecf4;
    font:15px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif;
    display:grid;place-items:center;-webkit-user-select:none;user-select:none}
  .box{display:flex;flex-direction:column;align-items:center;gap:18px}
  .logo{width:76px;height:76px;border-radius:22px;
    background:linear-gradient(135deg,#7c6cff,#4ad6c0);display:grid;place-items:center;
    box-shadow:0 18px 50px rgba(124,108,255,.28)}
  .logo span{width:0;height:0;margin-left:6px;
    border-left:24px solid #0e1014;border-top:15px solid transparent;border-bottom:15px solid transparent}
  h1{margin:0;font-size:20px;letter-spacing:.2px}
  p{margin:0;color:#98a2b4;font-size:13px;min-height:18px}
  .bar{width:220px;height:4px;border-radius:99px;background:#1d222c;overflow:hidden}
  .bar i{display:block;width:40%;height:100%;border-radius:99px;
    background:linear-gradient(90deg,#7c6cff,#4ad6c0);animation:run 1.1s ease-in-out infinite}
  @keyframes run{0%{transform:translateX(-100%)}100%{transform:translateX(320%)}}
</style></head>
<body><div class="box">
  <div class="logo"><span></span></div>
  <h1>SpriteAnim Studio</h1>
  <p id="hint">Запускаю сервер…</p>
  <div class="bar"><i></i></div>
</div>
<script>
  setTimeout(() => {
    const h = document.getElementById('hint');
    if (h) h.textContent = 'Первый запуск может занять несколько секунд…';
  }, 4000);
</script>
</body></html>
"""

ERROR_HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>SpriteAnim Studio</title>
<style>
  html,body{margin:0;height:100%;background:#0e1014;color:#e8ecf4;
    font:15px/1.6 "Segoe UI",system-ui,sans-serif;display:grid;place-items:center}
  .box{max-width:520px;padding:28px;background:#171b23;border:1px solid #262c38;border-radius:16px}
  h1{margin:0 0 10px;font-size:18px;color:#ff5d6c}
  p{margin:0 0 12px;color:#98a2b4;font-size:14px}
  code{color:#d7d2ff;background:#1d222c;border-radius:6px;padding:1px 6px}
  button{margin-top:6px;padding:9px 16px;border:0;border-radius:10px;cursor:pointer;
    background:linear-gradient(135deg,#7c6cff,#4ad6c0);color:#0e1014;font:600 14px inherit}
</style></head>
<body><div class="box">
  <h1>Сервер не поднялся</h1>
  <p>Порт <code>__PORT__</code> занят другим процессом или запуск прервался.
     Подробности — в <code>.cache/studio.log</code>.</p>
  <button onclick="location.href='__URL__'">Повторить</button>
</div></body></html>
"""


def log(*parts: object) -> None:
    try:
        print("[desktop]", *parts, flush=True)
    except Exception:  # noqa: BLE001
        pass


def port_open(timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", server.PORT), timeout):
            return True
    except OSError:
        return False


def wait_port(timeout: float = 40.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if port_open():
            return True
        time.sleep(0.15)
    return False


def screen_size() -> tuple[int, int]:
    try:
        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:  # noqa: BLE001
        return 1920, 1080


def allow_microphone(window) -> None:
    """WebView2 по умолчанию спрашивает разрешение на микрофон; для голосового
    ввода в этом приложении разрешаем сразу — звук никуда не отправляется."""
    try:
        from Microsoft.Web.WebView2.Core import (  # type: ignore[import-not-found]
            CoreWebView2PermissionKind,
            CoreWebView2PermissionState,
        )
        from System import Action  # type: ignore[import-not-found]

        control = None
        # boot() стартует параллельно с созданием окна: native появляется чуть позже.
        for _ in range(100):
            native = getattr(window, "native", None)
            control = getattr(native, "webview", None)
            if control is not None:
                break
            time.sleep(0.05)
        if control is None:
            log("окно ещё не готово — разрешение микрофона не подключено")
            return

        wanted = {CoreWebView2PermissionKind.Microphone}

        def attach() -> None:
            def wire(core) -> None:
                def on_permission(sender, args):  # noqa: ANN001, ARG001
                    try:
                        if args.PermissionKind in wanted:
                            args.State = CoreWebView2PermissionState.Allow
                            args.Handled = True
                    except Exception:  # noqa: BLE001
                        pass

                core.PermissionRequested += on_permission

            core = control.CoreWebView2
            if core is None:
                # WebView2 ещё инициализируется — подключаемся по событию.
                def on_ready(sender, args):  # noqa: ANN001, ARG001
                    try:
                        if args.IsSuccess:
                            wire(control.CoreWebView2)
                    except Exception:  # noqa: BLE001
                        pass

                control.CoreWebView2InitializationCompleted += on_ready
            else:
                wire(core)

        # CoreWebView2 существует только в UI-потоке: boot() работает в фоне.
        control.Invoke(Action(attach))
    except Exception as exc:  # noqa: BLE001
        log("разрешение микрофона не подключено:", exc)


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


def fallback_browser(started_server: bool) -> None:
    """Если WebView2 недоступен — открываем как раньше, окном Edge/Chrome --app."""
    browser = find_browser()
    if browser:
        args = [browser, f"--app={URL}", f"--user-data-dir={BASE / '.profile'}",
                "--window-size=1500,950", "--no-first-run", "--no-default-browser-check",
                "--disable-features=Translate"]
        try:
            subprocess.Popen(args).wait()
            if started_server:
                server.shutdown_app()
            return
        except OSError as exc:
            log("браузер не запустился:", exc)
    import webbrowser
    webbrowser.open(URL)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    if started_server:
        server.shutdown_app()


def message(text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10)
    except Exception:  # noqa: BLE001
        log(text)


def _api(path: str, method: str = "GET", timeout: float = 3.0):
    data = b"{}" if method.upper() != "GET" else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(URL + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ui_lang() -> str:
    try:
        data = json.loads((CACHE / "settings.json").read_text("utf-8"))
        return "en" if data.get("lang") == "en" else "ru"
    except Exception:  # noqa: BLE001
        return "ru"


def main() -> None:
    already = port_open()
    if already:
        log(f"сервер уже работает: {URL}")
    else:
        threading.Thread(target=server.serve, daemon=True, name="studio-server").start()

    try:
        import webview
    except Exception as exc:  # noqa: BLE001
        message(f"Не удалось загрузить pywebview:\n{exc}\n\nПриложение откроется в браузере.")
        fallback_browser(not already)
        return

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.settings["SHOW_DEFAULT_MENUS"] = False

    width, height = screen_size()
    win_w = max(900, min(1500, width - 80))
    win_h = max(620, min(950, height - 110))
    min_w = min(980, win_w)
    min_h = min(640, win_h)

    splash = SPLASH.replace("__PORT__", str(server.PORT)).replace("__URL__", URL)
    window = webview.create_window(
        TITLE,
        html=splash,
        width=win_w,
        height=win_h,
        min_size=(min_w, min_h),
        background_color="#0e1014",
        text_select=True,
        zoomable=True,
        hidden=SMOKE,
        confirm_close=False,
    )

    exit_state = {"done": False}

    def on_closing():
        """Спросить про фоновый ComfyUI: закрыть его или оставить."""
        if exit_state["done"]:
            return True
        try:
            info = _api("/api/comfy/owned", timeout=2.5)
        except Exception:  # noqa: BLE001
            return True
        if not (info.get("owned") and info.get("running")):
            return True
        if ui_lang() == "ru":
            title = "ComfyUI запущен в фоне"
            text = ("Приложение запустило ComfyUI в фоновом режиме.\n\n"
                    "«ОК» — закрыть ComfyUI и выйти.\n"
                    "«Отмена» — оставить его работать и выйти.")
        else:
            title = "ComfyUI is running in the background"
            text = ("The app started ComfyUI in the background.\n\n"
                    "OK — stop ComfyUI and exit.\n"
                    "Cancel — keep it running and exit.")
        try:
            stop_it = window.create_confirmation_dialog(title, text)
        except Exception as exc:  # noqa: BLE001
            log("окно вопроса не показалось:", exc)
            stop_it = False
        if stop_it:
            try:
                _api("/api/comfy/stop", method="POST", timeout=25)
            except Exception as exc:  # noqa: BLE001
                log("ComfyUI не остановился:", exc)
        exit_state["done"] = True
        return True

    if not SMOKE:
        window.events.closing += on_closing

    def boot() -> None:
        if not already and not wait_port():
            log("сервер не поднялся")
            window.load_html(ERROR_HTML.replace("__PORT__", str(server.PORT)).replace("__URL__", URL))
            if SMOKE:
                window.destroy()
            return
        allow_microphone(window)
        log(f"окно -> {URL}")
        window.load_url(URL)
        if SMOKE:
            threading.Timer(2.0, window.destroy).start()

    try:
        webview.start(
            boot,
            debug=DEBUG,
            icon=str(ICON) if ICON.is_file() else None,
            private_mode=False,
            storage_path=str(BASE / ".profile"),
        )
    except Exception as exc:  # noqa: BLE001
        log("окно не открылось:", exc)
        message(
            "Не удалось открыть окно приложения (WebView2).\n"
            "Установите Microsoft Edge WebView2 Runtime и запустите снова.\n\n"
            f"Подробности: {CACHE / 'studio.log'}"
        )
        fallback_browser(not already)
        return

    log("окно закрыто")
    if not already:
        server.shutdown_app()


if __name__ == "__main__":
    main()
