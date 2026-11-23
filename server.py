#!/usr/bin/env python3
"""SpriteAnim Studio — локальная надстройка над ComfyUI для спрайтовых анимаций.

Без внешних зависимостей: только стандартная библиотека Python 3.11+.
Запуск:  python server.py
Проверка конвертации воркфлоу:  python server.py --check
"""
from __future__ import annotations

import array
import base64
import io
import json
import mimetypes
import os
import random
import re
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# В собранной версии (PyInstaller) рядом с .exe лежит папка для записи,
# а ресурсы распакованы в _internal. В обычном запуске это одна и та же папка.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    DATA = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    ROOT = Path(sys.executable).resolve().parent
else:
    DATA = ROOT
# Куда складывать результаты: по умолчанию папка output рядом с программой.
# В настройках можно выбрать другую (сохраняется в .cache/settings.json).
OUTPUT_DIR = Path(os.environ.get("SPRITE_OUTPUT_DIR") or (ROOT / "output"))
SETTINGS_FILE = ROOT / ".cache" / "settings.json"
_settings_lock = threading.Lock()
_settings: dict = {"output_dir": str(OUTPUT_DIR)}


def _load_settings():
    try:
        data = json.loads(SETTINGS_FILE.read_text("utf-8"))
        if isinstance(data, dict):
            for key in ("output_dir", "models_dir", "agent_dir"):
                if data.get(key):
                    _settings[key] = str(data[key])
            if data.get("theme") in THEMES:
                _settings["theme"] = str(data["theme"])
            if data.get("lang") in LANGS:
                _settings["lang"] = str(data["lang"])
            if data.get("comfy_auto"):
                _settings["comfy_auto"] = True
            if data.get("comfy_cmd"):
                _settings["comfy_cmd"] = str(data["comfy_cmd"])
            if data.get("comfy_cmdline"):
                _settings["comfy_cmdline"] = str(data["comfy_cmdline"])
            if data.get("comfy_cwd"):
                _settings["comfy_cwd"] = str(data["comfy_cwd"])
            owned = data.get("comfy_owned")
            if isinstance(owned, dict) and owned.get("pid"):
                _settings["comfy_owned"] = owned
            if "lan" in data:
                _settings["lan"] = bool(data.get("lan"))
    except Exception:  # noqa: BLE001
        pass


def _save_settings() -> None:
    try:
        SETTINGS_FILE.parent.mkdir(exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(_settings, ensure_ascii=False, indent=1), "utf-8")
    except OSError:
        pass


def output_dir() -> Path:
    return Path(_settings.get("output_dir") or OUTPUT_DIR)


def sheets_dir() -> Path:
    return output_dir() / "sheets"


def save_sheet(name: str, blob: bytes, columns: int = 0, rows: int = 0,
               cw: int = 0, ch: int = 0, count: int = 0,
               crop: str = "", src: str = "", origin: str = "",
               pad: str = "", pivot: str = "") -> dict:
    """Сохраняет готовый спрайт-лист и его JSON в output/sheets/<имя>-<время>."""
    if not blob or len(blob) < 100:
        raise ValueError("пустой лист")
    slug = slugify(name, "sprite")
    run = time.strftime("%Y%m%d-%H%M%S")
    dest = sheets_dir() / f"{slug}-{run}"
    dest.mkdir(parents=True, exist_ok=True)
    png = dest / f"{slug}-sheet.png"
    png.write_bytes(blob)
    columns = max(0, int(columns or 0))
    rows = max(0, int(rows or 0))
    cw = max(0, int(cw or 0))
    ch = max(0, int(ch or 0))
    count = max(0, int(count or 0))

    def nums(raw: str, keys: tuple[str, ...]) -> dict:
        try:
            values = [int(v) for v in str(raw or "").split(",")]
        except ValueError:
            return {}
        if len(values) != len(keys):
            return {}
        return dict(zip(keys, values))

    cells = []
    if columns and cw:
        for i in range(count):
            cells.append({"i": i, "x": (i % columns) * cw,
                          "y": (i // columns) * ch, "w": cw, "h": ch})
    atlas = {"image": png.name, "columns": columns, "rows": rows,
             "count": count, "frame": {"w": cw, "h": ch}, "frames": cells}
    source = nums(src, ("w", "h"))
    if source:
        atlas["source"] = source
    box = nums(crop, ("x", "y", "w", "h"))
    if box:
        atlas["crop"] = box

    def floats(raw: str, keys: tuple[str, ...]) -> dict:
        try:
            values = [float(v) for v in str(raw or "").split(",")]
        except ValueError:
            return {}
        if len(values) != len(keys):
            return {}
        return dict(zip(keys, values))

    try:
        pad_px = max(0, min(64, int(str(pad or "0").strip() or 0)))
    except ValueError:
        pad_px = 0
    atlas["pad"] = pad_px
    pivot_xy = floats(pivot, ("x", "y"))
    if pivot_xy:
        atlas["pivot"] = pivot_xy
        atlas["pivot_px"] = {"x": round(pivot_xy["x"] * cw),
                             "y": round(pivot_xy["y"] * ch)}
    if origin:
        try:
            extra = json.loads(origin)
        except Exception:  # noqa: BLE001
            extra = None
        if isinstance(extra, dict) and extra:
            atlas["origin"] = extra
    js = dest / f"{slug}-sheet.json"
    js.write_text(json.dumps(atlas, ensure_ascii=False, indent=1), "utf-8")
    return {"dir": str(dest), "png": str(png), "json": str(js), "size": len(blob)}


def default_models_dir() -> str:
    """Папка моделей ComfyUI, которую он сам показывает."""
    roots = comfy_folder_paths().get("diffusion_models") or []
    first = next((r for r in roots if r), "")
    return str(Path(first).parent) if first else ""


def default_agent_dir() -> str:
    legacy = Path("E:/ComfyModelsHub/models/MinimaxH3_assistant")
    return str(legacy if legacy.is_dir() else (ROOT / "models" / "agent"))


def models_dir() -> str:
    return str(_settings.get("models_dir") or default_models_dir())


THEMES = ("studio", "maker", "light")
LANGS = ("ru", "en")


def settings_info() -> dict:
    return {
        "output_dir": str(output_dir()), "default_dir": str(OUTPUT_DIR),
        "models_dir": models_dir(), "models_default": default_models_dir(),
        "agent_dir": str(agent_home()), "agent_default": default_agent_dir(),
        "theme": _settings.get("theme") or "studio", "themes": list(THEMES),
        "lang": _settings.get("lang") or "", "langs": list(LANGS),
        "comfy_auto": bool(_settings.get("comfy_auto")),
        "comfy_cmd": str(_settings.get("comfy_cmd") or ""),
        "comfy_launcher": comfy_launcher_path(),
        "comfy_remembered": bool(_settings.get("comfy_cmdline")),
        "lan": lan_enabled(),
    }


# ------------------------------------------------------- обновления
APP_VERSION = "0.4.2"
GITHUB_REPO = "MaxKeks88/spriteanim-studio"
UPDATE_CACHE_TTL = 600
UPDATE_DIR = ROOT / ".cache" / "update"
_update_cache: dict = {"ts": 0.0, "data": None}
_update_lock = threading.Lock()


def _ver_tuple(text: str) -> tuple:
    parts = re.findall(r"\d+", str(text or ""))
    return tuple(int(p) for p in parts[:4]) or (0,)


def update_check(force: bool = False) -> dict:
    """Сравнивает текущую версию с последним релизом на GitHub."""
    now = time.time()
    with _update_lock:
        cached = _update_cache["data"]
        if not force and cached and now - _update_cache["ts"] < UPDATE_CACHE_TTL:
            return cached

    latest, asset, page, notes, error = None, None, None, "", ""
    fake = os.environ.get("SPRITE_FAKE_LATEST")
    if fake:
        latest = fake.strip().lstrip("vV")
        page = f"https://github.com/{GITHUB_REPO}/releases"
        asset = os.environ.get("SPRITE_FAKE_ASSET") or None
    else:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "User-Agent": f"SpriteAnimStudio/{APP_VERSION}",
            "Accept": "application/vnd.github+json",
        })
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            latest = str(data.get("tag_name") or "").strip().lstrip("vV") or None
            page = data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"
            notes = (data.get("body") or "").strip()
            for item in data.get("assets") or []:
                name = str(item.get("name") or "").lower()
                if name.endswith(".exe") and "setup" in name:
                    asset = item.get("browser_download_url")
                    break
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

    available = bool(latest and _ver_tuple(latest) > _ver_tuple(APP_VERSION))
    result = {
        "current": APP_VERSION,
        "latest": latest,
        "available": available,
        "asset": asset,
        "page": page or f"https://github.com/{GITHUB_REPO}/releases",
        "notes": notes[:4000],
        "error": error,
    }
    with _update_lock:
        _update_cache["ts"] = now
        _update_cache["data"] = result
    return result


def update_install() -> dict:
    """Скачивает установщик последней версии и запускает его."""
    info = update_check()
    if not info.get("available"):
        raise RuntimeError("обновление не найдено")
    asset = info.get("asset")
    if not asset:
        raise RuntimeError("в релизе нет установщика")
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPDATE_DIR / f"SpriteAnimStudio-Setup-{info['latest']}.exe"
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(asset, headers={
        "User-Agent": f"SpriteAnimStudio/{APP_VERSION}",
    })
    with urllib.request.urlopen(req, timeout=180) as resp, tmp.open("wb") as fh:
        shutil.copyfileobj(resp, fh, 1024 * 256)
    if tmp.stat().st_size < 1_000_000:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("установщик скачался не полностью")
    tmp.replace(dest)

    def run() -> None:
        time.sleep(1.2)
        try:
            subprocess.Popen(
                [str(dest), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                close_fds=True,
            )
        except OSError:
            return
        time.sleep(2.0)
        shutdown_app()

    threading.Thread(target=run, daemon=True, name="studio-update").start()
    return {"ok": True, "version": info["latest"], "file": str(dest)}


def _check_dir(raw: str, label: str, subs: tuple = ()) -> Path:
    raw = str(raw or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("укажите папку")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise ValueError(f"нужен полный путь для {label}, например E:\\SpriteAnim")
    try:
        p.mkdir(parents=True, exist_ok=True)
        for sub in subs:
            if sub:
                (p / sub).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"не удалось создать папку: {exc}") from exc
    return p


def apply_settings(payload: dict) -> dict:
    """Сохраняет переданные поля. Пустая строка — вернуть значение по умолчанию."""
    changed = False
    with _settings_lock:
        if "output_dir" in payload:
            raw = str(payload.get("output_dir") or "").strip()
            if not raw:
                _settings["output_dir"] = str(OUTPUT_DIR)
            else:
                p = _check_dir(raw, "результатов", ("images", "background", "animation"))
                _settings["output_dir"] = str(p)
            changed = True
        if "models_dir" in payload:
            raw = str(payload.get("models_dir") or "").strip()
            if not raw:
                _settings.pop("models_dir", None)
            else:
                _settings["models_dir"] = str(_check_dir(raw, "моделей"))
            changed = True
        if "theme" in payload:
            theme = str(payload.get("theme") or "").strip()
            if theme and theme not in THEMES:
                raise ValueError("неизвестная тема")
            _settings["theme"] = theme or "studio"
            changed = True
        if "lang" in payload:
            lang = str(payload.get("lang") or "").strip()
            if lang and lang not in LANGS:
                raise ValueError("неизвестный язык")
            _settings["lang"] = lang
            changed = True
        if "agent_dir" in payload:
            raw = str(payload.get("agent_dir") or "").strip()
            if not raw:
                _settings.pop("agent_dir", None)
            else:
                _settings["agent_dir"] = str(_check_dir(raw, "агента", ("models", "llama.cpp")))
            _agent_home_cache.clear()
            changed = True
        if "comfy_auto" in payload:
            _settings["comfy_auto"] = bool(payload.get("comfy_auto"))
            changed = True
        if "comfy_cmd" in payload:
            raw = str(payload.get("comfy_cmd") or "").strip()
            if not raw:
                _settings.pop("comfy_cmd", None)
            else:
                p = Path(raw).expanduser()
                if not p.is_file():
                    raise ValueError("файл запуска ComfyUI не найден")
                _settings["comfy_cmd"] = str(p)
            _launcher_cache["t"] = 0.0
            changed = True
        if "lan" in payload:
            _settings["lan"] = bool(payload.get("lan"))
            changed = True
        if changed:
            _save_settings()
    return settings_info()


def list_dirs(raw: str) -> dict:
    """Содержимое папки для встроенного выбора каталога (без окон Windows)."""
    drives = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            try:
                if root.exists():
                    drives.append({"name": f"{letter}:", "path": str(root)})
            except OSError:
                continue
    else:
        drives.append({"name": "/", "path": "/"})

    raw = str(raw or "").strip().strip('"').strip("'")
    if not raw:
        return {"path": "", "parent": "", "drives": drives, "dirs": [], "error": ""}
    p = Path(raw).expanduser()
    if not p.is_absolute():
        return {"path": raw, "parent": "", "drives": drives, "dirs": [],
                "error": "нужен полный путь"}
    try:
        p = p.resolve()
    except OSError:
        p = p
    if not p.is_dir():
        return {"path": str(p), "parent": str(p.parent), "drives": drives, "dirs": [],
                "error": "папка не найдена"}
    dirs = []
    try:
        for entry in p.iterdir():
            try:
                if entry.is_dir():
                    dirs.append({"name": entry.name, "path": str(entry)})
            except OSError:
                continue
    except PermissionError:
        return {"path": str(p), "parent": str(p.parent), "drives": drives, "dirs": [],
                "error": "нет доступа к папке"}
    except OSError as exc:
        return {"path": str(p), "parent": str(p.parent), "drives": drives, "dirs": [],
                "error": str(exc)}
    dirs.sort(key=lambda d: d["name"].lower())
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else "",
            "drives": drives, "dirs": dirs, "error": ""}
_load_settings()
WF_DIR = DATA / "workflows"
UI_DIR = DATA / "ui"
CACHE_DIR = ROOT / ".cache"
AGENT_LOG = CACHE_DIR / "agent.log"

COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
HOST = os.environ.get("SPRITE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SPRITE_PORT", "8189"))
LAN_PORT = 8190
APP_PACKAGE = "spriteanim-studio"


def lan_enabled() -> bool:
    """Доступ с телефона по локальной сети (по умолчанию включён)."""
    value = _settings.get("lan")
    return True if value is None else bool(value)


def bind_host() -> str:
    """Адрес, на котором слушает сервер: localhost или вся сеть."""
    env = os.environ.get("SPRITE_HOST")
    if env:
        return env
    return "0.0.0.0" if lan_enabled() else "127.0.0.1"


def local_ips() -> list[str]:
    """IPv4-адреса машины в локальной сети (без 127.*)."""
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = str(info[4][0])
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = str(s.getsockname()[0])
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.insert(0, ip)
    except OSError:
        pass
    return ips


def net_info() -> dict:
    ips = local_ips()
    return {
        "app": APP_PACKAGE,
        "name": "SpriteAnim Studio",
        "version": APP_VERSION,
        "port": PORT,
        "discovery": LAN_PORT,
        "lan": lan_enabled(),
        "host": ips[0] if ips else "",
        "urls": [f"http://{ip}:{PORT}" for ip in ips],
    }

# ---------------------------------------------------------------- ComfyUI API

# Типы, которые всегда приходят связью (link), а не виджетом с значением.
LINK_ONLY = {
    "MODEL", "CLIP", "VAE", "IMAGE", "MASK", "LATENT", "CONDITIONING",
    "CONTROL_NET", "SIGMAS", "SAMPLER", "GUIDER", "NOISE", "VIDEO", "AUDIO",
    "UPSCALE_MODEL", "CLIP_VISION", "STYLE_MODEL", "VAE_APPROX", "CLIP_VISION_OUTPUT",
    "PHOTOMAKER", "GLIGEN", "SIGMAS", "LATENT_UPSCALE",
}

_obj_cache: dict = {"t": 0.0, "data": None}
_comfy_seen: dict = {"online": None}


def _http_json(url: str, payload=None, timeout: float = 60.0):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def comfy_json(path: str, payload=None, timeout: float = 60.0):
    return _http_json(COMFY + path, payload, timeout)


def object_info(force: bool = False) -> dict:
    if not force and _obj_cache["data"] and time.time() - _obj_cache["t"] < 120:
        return _obj_cache["data"]
    data = comfy_json("/object_info", timeout=90)
    _obj_cache.update(t=time.time(), data=data)
    return data


def comfy_online() -> bool:
    global _folder_paths_t
    try:
        comfy_json("/system_stats", timeout=3)
        if _comfy_seen["online"] is False:
            # ComfyUI поднялся позже приложения — старый кэш моделей уже неверен.
            _obj_cache.update(t=0.0, data={})
            _folder_paths_cache.clear()
            _folder_paths_t = 0.0
        _comfy_seen["online"] = True
        return True
    except Exception:
        _comfy_seen["online"] = False
        return False


def comfy_version() -> str:
    try:
        st = comfy_json("/system_stats", timeout=5)
        return str((st.get("system") or {}).get("comfyui_version") or "")
    except Exception:
        return ""


# ------------------------------------------------------- запуск ComfyUI
# Приложение умеет поднять ComfyUI само: portable-сборку из своей папки,
# ярлык Comfy Desktop из меню «Пуск» или путь, выбранный в настройках.
_launcher_cache: dict = {"t": 0.0, "path": None}
_launcher_lock = threading.Lock()
_capture_state: dict = {"tried": 0.0}


def _start_menu_links() -> list[Path]:
    out: list[Path] = []
    for env in ("APPDATA", "ProgramData"):
        base = os.environ.get(env)
        if not base:
            continue
        root = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if not root.is_dir():
            continue
        try:
            out += [p for p in root.rglob("*.lnk") if "comfy" in p.name.lower()]
        except OSError:
            continue
    return out


def comfy_launcher() -> Path | None:
    """Чем запускать ComfyUI: настройка, portable-сборка, ярлык или типовое место."""
    now = time.time()
    with _launcher_lock:
        if now - float(_launcher_cache["t"] or 0) < 60:
            return _launcher_cache["path"]      # «не нашли» тоже кэшируем
        found: Path | None = None
        custom = str(_settings.get("comfy_cmd") or "").strip()
        if custom:
            p = Path(custom).expanduser()
            if p.is_file():
                found = p
        if found is None:
            base = comfy_portable_dir()
            if base.is_dir():
                found = next((p for p in sorted(base.glob("run_*.bat")) if p.is_file()), None)
        if found is None:
            links = sorted(_start_menu_links(),
                           key=lambda p: (0 if "desktop" in p.name.lower() else 1, p.name.lower()))
            found = links[0] if links else None
        if found is None:
            local = os.environ.get("LOCALAPPDATA") or ""
            for cand in (Path(local) / "Programs" / "ComfyUI" / "ComfyUI.exe",
                         Path(local) / "Programs" / "@comfyorgcomfyui-electron" / "ComfyUI.exe",
                         Path("C:/Program Files/ComfyUI/ComfyUI.exe")):
                if cand.is_file():
                    found = cand
                    break
        _launcher_cache.update(t=now, path=found)
        return found


def comfy_start() -> dict:
    """Запускает ComfyUI в фоне; если он уже работает — ничего не делает."""
    if comfy_online():
        return {"ok": True, "already": True}
    remembered = str(_settings.get("comfy_cmdline") or "").strip()
    if remembered:
        cwd = str(_settings.get("comfy_cwd") or "")
        if not cwd or not Path(cwd).is_dir():
            cwd = _cmdline_cwd(remembered)
        try:
            proc = subprocess.Popen(remembered, cwd=cwd or None, shell=True,
                                    creationflags=0x08000000,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    stdin=subprocess.DEVNULL)
        except OSError as exc:
            raise RuntimeError(f"не удалось запустить ComfyUI: {exc}") from exc
        with _settings_lock:
            _settings["comfy_owned"] = {"pid": proc.pid, "ts": time.time(), "cmd": remembered}
            _save_settings()
        return {"ok": True, "cmd": remembered, "cwd": cwd, "mode": "command", "owned": True}
    exe = comfy_launcher()
    if exe is None:
        raise RuntimeError("не нашёл программу ComfyUI — укажите её в настройках")
    _clear_owned()
    flags = 0x00000008 if os.name == "nt" else 0
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "/MIN", str(exe)],
                         cwd=str(exe.parent), creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise RuntimeError(f"не удалось запустить ComfyUI: {exc}") from exc
    return {"ok": True, "cmd": str(exe), "mode": "file"}


def comfy_process_cmdline() -> str:
    """Командная строка работающего сервера ComfyUI (Windows)."""
    if os.name != "nt":
        return ""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
          "Where-Object { $_.CommandLine -match 'ComfyUI\\\\main.py' } | "
          "Select-Object -First 1 -ExpandProperty CommandLine")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=20, creationflags=0x08000000)
    except Exception:  # noqa: BLE001
        return ""
    return (out.stdout or "").strip()


def _cmdline_cwd(cmdline: str) -> str:
    """Рабочая папка для сохранённой команды: там, где лежит ComfyUI\\main.py."""
    raw = (cmdline or "").strip()
    if not raw:
        return ""
    if raw.startswith('"'):
        end = raw.find('"', 1)
        exe = raw[1:end] if end > 0 else raw.strip('"')
    else:
        exe = raw.split(" ", 1)[0]
    p = Path(exe)
    for cand in (p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent):
        try:
            if (cand / "ComfyUI" / "main.py").is_file():
                return str(cand)
        except OSError:
            continue
    return str(p.parent)


def comfy_capture() -> bool:
    """Запоминает команду запуска работающего ComfyUI — ею потом поднимаем его сами."""
    now = time.time()
    if now - float(_capture_state.get("tried") or 0) < 120:
        return False
    _capture_state["tried"] = now
    cmdline = comfy_process_cmdline()
    if not cmdline:
        return False
    cwd = _cmdline_cwd(cmdline)
    with _settings_lock:
        _settings["comfy_cmdline"] = cmdline
        _settings["comfy_cwd"] = cwd
        _save_settings()
    return True


def comfy_launcher_path() -> str:
    """Путь к программе запуска (для поля настроек)."""
    custom = str(_settings.get("comfy_cmd") or "").strip()
    if custom:
        return custom
    p = comfy_launcher()
    return str(p) if p else ""


def _proc_info(pid: int) -> dict:
    """Живой ли процесс и что у него в командной строке (Windows)."""
    if os.name != "nt" or not pid:
        return {"alive": False}
    ps = (f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\"; "
          "if ($p) { @{ cmd = [string]$p.CommandLine; "
          "created = [double]([DateTimeOffset]$p.CreationDate).ToUnixTimeSeconds() } "
          "| ConvertTo-Json -Compress }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=15, creationflags=0x08000000)
        raw = (out.stdout or "").strip()
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict) or not data:
            return {"alive": False}
        return {"alive": True, "cmd": str(data.get("cmd") or ""),
                "created": float(data.get("created") or 0)}
    except Exception:  # noqa: BLE001
        return {"alive": False}


def _clear_owned() -> None:
    with _settings_lock:
        if _settings.pop("comfy_owned", None) is not None:
            _save_settings()


def comfy_owned() -> dict:
    """Сервер запущен именно приложением? Проверяем PID и время старта."""
    rec = _settings.get("comfy_owned")
    if not isinstance(rec, dict) or not rec.get("pid"):
        return {"owned": False}
    pid = int(rec.get("pid") or 0)
    info = _proc_info(pid)
    if not info.get("alive"):
        _clear_owned()
        return {"owned": False}
    if "comfyui" not in str(info.get("cmd") or "").lower():
        return {"owned": False}
    created = float(info.get("created") or 0)
    ts = float(rec.get("ts") or 0)
    if created and ts and abs(created - ts) > 30:
        return {"owned": False}          # PID успели переиспользовать
    return {"owned": True, "pid": pid}


def comfy_stop() -> dict:
    """Останавливает ComfyUI, но только если его запустило приложение."""
    info = comfy_owned()
    if not info.get("owned"):
        raise RuntimeError("ComfyUI запущен не приложением — закройте его вручную")
    pid = int(info["pid"])
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=25, creationflags=flags)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"не удалось остановить ComfyUI: {exc}") from exc
    _clear_owned()
    deadline = time.time() + 10
    while time.time() < deadline:
        if not comfy_online():
            return {"ok": True}
        time.sleep(0.5)
    return {"ok": True, "warning": "процесс завершается"}


# ------------------------------------------------- активные задания (очередь)
# Студия помнит, что поставила в ComfyUI: после её перезапуска задания подхватываются.
JOBS_FILE = ROOT / ".cache" / "jobs.json"
_jobs_lock = threading.Lock()


def jobs_load() -> dict:
    try:
        data = json.loads(JOBS_FILE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def jobs_save(data: dict):
    try:
        JOBS_FILE.parent.mkdir(exist_ok=True)
        tmp = JOBS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        tmp.replace(JOBS_FILE)
    except OSError:
        pass


def jobs_add(entry: dict):
    if not entry.get("id"):
        return
    with _jobs_lock:
        data = jobs_load()
        data[str(entry["id"])] = entry
        jobs_save(data)


def jobs_remove(pid: str):
    with _jobs_lock:
        data = jobs_load()
        if data.pop(str(pid), None) is not None:
            jobs_save(data)


def jobs_active() -> list:
    """Активные задания с состоянием ComfyUI: done / running / queued / lost."""
    data = jobs_load()
    now = time.time()
    out = []
    for pid, j in data.items():
        age = now - float(j.get("ts") or 0)
        if age > 24 * 3600:
            continue
        if j.get("kind") == "upscale":
            out.append({**j, "state": j.get("state") or "queued"})
            continue
        state = "lost"
        try:
            h = comfy_json(f"/history/{pid}", timeout=5)
            if pid in h:
                state = "done"
        except Exception:  # noqa: BLE001
            pass
        if state != "done":
            try:
                q = comfy_json("/queue", timeout=5)
                running = [x[1] for x in (q.get("queue_running") or []) if len(x) > 1]
                pending = [x[1] for x in (q.get("queue_pending") or []) if len(x) > 1]
                if pid in running:
                    state = "running"
                elif pid in pending or age < 90:
                    state = "queued"
            except Exception:  # noqa: BLE001
                state = "queued" if age < 90 else "lost"
        out.append({**j, "state": state})
    out.sort(key=lambda j: j.get("ts") or 0)
    return out


# ------------------------------------------------------------ история прогонов
RUNS_FILE = ROOT / ".cache" / "runs.jsonl"
_runs_lock = threading.Lock()
RUN_KEYS = ("kind", "id", "ts", "model", "prompt", "seed", "steps", "width", "height",
            "base", "aspect", "ref", "refs", "mode", "name", "frames", "resolution",
            "out", "outKind", "thumb", "seconds")


def runs_add(entry: dict) -> dict:
    """Дописывает прогон в историю (.cache/runs.jsonl)."""
    rec = {k: entry.get(k) for k in RUN_KEYS}
    rec = {k: v for k, v in rec.items() if v not in (None, "")}
    rec.setdefault("ts", time.time())
    with _runs_lock:
        try:
            RUNS_FILE.parent.mkdir(exist_ok=True)
            with RUNS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise RuntimeError(f"не удалось записать историю: {exc}") from exc
    return {"ok": True}


def runs_list(limit: int = 60, kind: str = "") -> list:
    """Новые сверху, без дублей по id задания."""
    if not RUNS_FILE.is_file():
        return []
    try:
        lines = RUNS_FILE.read_text("utf-8").splitlines()
    except OSError:
        return []
    out, seen = [], set()
    for line in reversed(lines[-4000:]):
        try:
            e = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if kind and e.get("kind") != kind:
            continue
        key = e.get("id") or json.dumps(e, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------ прогресс из ComfyUI
# ComfyUI отдаёт события по WebSocket (/ws?clientId=...): executing, progress,
# бинарные превью кадра. Своего WS-клиента пишем сами — внешних пакетов нет.
_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()

NODE_LABEL = {
    "KSampler": "рисую",
    "SamplerCustomAdvanced": "рисую",
    "VAEDecode": "собираю кадры",
    "VAEEncode": "готовлю референс",
    "SpriteChromaKey": "вырезаю фон",
    "SpriteLoopTrim": "обрезаю цикл",
    "SaveImage": "сохраняю кадры",
    "SaveImageAdvanced": "сохраняю",
    "SaveVideo": "собираю видео",
    "MiniMaxH3ImageToVideo": "готовлю сцену",
    "MiniMaxH3ImageConditioning": "читаю промпт",
    "TextEncodeQwenImage21": "читаю промпт",
    "LoadImage": "загружаю картинку",
    "EmptyLatentImage": "готовлю холст",
    "EmptyFlux2LatentImage": "готовлю холст",
    "QwenImage21Cache": "грею модель",
}


class _WS:
    """Минимальный WebSocket-клиент: рукопожатие, чтение кадров, ping/pong."""

    def __init__(self, url: str, timeout: float = 10.0):
        u = urllib.parse.urlparse(url)
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port or 80
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        req = (f"GET {path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise OSError("ws: соединение закрыто при рукопожатии")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise OSError("ws: сервер не переключил протокол")

    def _take(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise OSError("ws: соединение закрыто")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self, timeout: float = 1.0):
        self.sock.settimeout(timeout)
        try:
            b = self._take(2)
        except socket.timeout:
            return None
        b1, b2 = b[0], b[1]
        opcode = b1 & 0x0F
        ln = b2 & 0x7F
        if ln == 126:
            ln = int.from_bytes(self._take(2), "big")
        elif ln == 127:
            ln = int.from_bytes(self._take(8), "big")
        mask = self._take(4) if (b2 & 0x80) else None
        payload = self._take(ln) if ln else b""
        if mask:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        return opcode, payload

    def send(self, opcode: int, payload: bytes = b""):
        mask = os.urandom(4)
        data = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        n = len(payload)
        if n < 126:
            head = bytes([0x80 | opcode, 0x80 | n])
        elif n < 65536:
            head = bytes([0x80 | opcode, 0x80 | 126]) + n.to_bytes(2, "big")
        else:
            head = bytes([0x80 | opcode, 0x80 | 127]) + n.to_bytes(8, "big")
        self.sock.sendall(head + mask + data)

    def close(self):
        try:
            self.send(0x8)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.sock.close()
        except Exception:  # noqa: BLE001
            pass


def _progress_set(pid: str, **kw):
    with _progress_lock:
        st = _progress.setdefault(pid, {})
        st.update(kw)
        st["ts"] = time.time()


def progress_snapshot(pid: str) -> dict:
    with _progress_lock:
        return dict(_progress.get(pid) or {})


def _monitor_job(prompt_id: str, client_id: str, graph: dict):
    nodes = {str(k): str((v or {}).get("class_type") or "") for k, v in (graph or {}).items()}
    _progress_set(prompt_id, state="running", label="в очереди", step=0, total=0)
    deadline = time.time() + 3600
    try:
        ws = _WS(f"ws://127.0.0.1:8188/ws?clientId={client_id}")
    except Exception:  # noqa: BLE001
        return
    try:
        while time.time() < deadline:
            msg = ws.recv(1.0)
            if msg is None:
                if progress_snapshot(prompt_id).get("state") in ("done", "error"):
                    break
                continue
            op, payload = msg
            if op == 9:                     # ping
                ws.send(0xA, payload)
                continue
            if op == 8:                     # close
                break
            if op == 2:                     # бинарное превью кадра
                if len(payload) > 8:
                    # ComfyUI кладёт перед картинкой служебные байты; ищем сигнатуру.
                    img = payload
                    for magic in (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n"):
                        pos = payload.find(magic)
                        if pos >= 0:
                            img = payload[pos:]
                            break
                    else:
                        img = payload[4:]
                    mime = "image/png" if img[:4] == b"\x89PNG" else "image/jpeg"
                    _progress_set(prompt_id, preview=f"data:{mime};base64,"
                                  + base64.b64encode(img).decode())
                continue
            if op != 1:
                continue
            try:
                ev = json.loads(payload.decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001
                continue
            typ = ev.get("type")
            data = ev.get("data") or {}
            pid = data.get("prompt_id")
            if pid and pid != prompt_id:
                continue
            if typ == "executing":
                node = data.get("node")
                if node in (None, ""):
                    _progress_set(prompt_id, state="done", label="готово", step=0, total=0)
                    break
                cls = nodes.get(str(node), "")
                _progress_set(prompt_id, node=str(node), label=NODE_LABEL.get(cls, "работаю"),
                              step=0, total=0)
            elif typ == "progress":
                _progress_set(prompt_id, step=int(data.get("value") or 0),
                              total=int(data.get("max") or 0))
            elif typ == "execution_error":
                _progress_set(prompt_id, state="error",
                              error=str(data.get("exception_message") or "ошибка ComfyUI"))
            elif typ in ("execution_success", "execution_interrupted"):
                _progress_set(prompt_id, state="done" if typ == "execution_success" else "error",
                              label="готово")
                break
    except Exception:  # noqa: BLE001
        pass
    finally:
        ws.close()
        st = progress_snapshot(prompt_id)
        if st.get("state") == "running":
            _progress_set(prompt_id, state="done")


def start_progress(prompt_id: str, client_id: str, graph: dict):
    if prompt_id:
        threading.Thread(target=_monitor_job, args=(prompt_id, client_id, graph),
                         daemon=True).start()


def upload_image(name: str, blob: bytes) -> str:
    """POST /upload/image (multipart вручную, без сторонних пакетов)."""
    boundary = "----SpriteAnim" + uuid.uuid4().hex
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "character.png"
    body = io.BytesIO()

    def part(text: str):
        body.write(text.encode("utf-8"))

    part(f"--{boundary}\r\n")
    part('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % safe)
    part("Content-Type: application/octet-stream\r\n\r\n")
    body.write(blob)
    part(f"\r\n--{boundary}\r\n")
    part('Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue')
    part(f"\r\n--{boundary}--\r\n")

    req = urllib.request.Request(
        COMFY + "/upload/image",
        data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read().decode("utf-8"))
    sub = (res.get("subfolder") or "").strip("/")
    return f"{sub}/{res['name']}" if sub else res["name"]


# ---------------------------------------------------------- воркфлоу → граф

def widget_names(cls_info: dict) -> list[str]:
    """Имена полей-виджетов ноды в порядке объявления (без входов-связей)."""
    names: list[str] = []
    spec = (cls_info or {}).get("input") or {}
    for section in ("required", "optional"):
        for name, desc in (spec.get(section) or {}).items():
            t = desc[0] if isinstance(desc, (list, tuple)) and desc else desc
            if isinstance(t, str) and t in LINK_ONLY:
                continue
            names.append(name)
    return names


def declared_inputs(cls_info: dict) -> set[str]:
    spec = (cls_info or {}).get("input") or {}
    names: set[str] = set()
    for section in ("required", "optional"):
        names |= set((spec.get(section) or {}).keys())
    return names


def ui_to_api(wf: dict, info: dict, warn: list[str]) -> dict:
    """UI-формат ComfyUI (nodes/links) → API-формат (prompt)."""
    links = {l[0]: l for l in (wf.get("links") or []) if isinstance(l, list)}
    graph: dict = {}
    for node in wf.get("nodes") or []:
        cls = node.get("type")
        if cls in ("Note", "MarkdownNote"):
            continue
        if node.get("mode") in (2, 4):
            warn.append(f"нода #{node.get('id')} {cls}: режим {node.get('mode')} (mute/bypass) — прототип его не поддерживает")
            continue
        if cls not in info:
            warn.append(f"нода #{node.get('id')}: ComfyUI не знает тип {cls}")
            continue
        inputs: dict = {}
        linked = {i.get("name") for i in (node.get("inputs") or []) if i.get("link") is not None}
        declared = declared_inputs(info[cls])
        # Основной источник — widgets_values: это то, что читает сам ComfyUI.
        # widgets_values_named может отставать от него (например, после правки
        # графа в другой программе), поэтому он только дополняет недостающее
        # (вложенные поля вида format.codec).
        full = widget_names(info[cls])
        values = node.get("widgets_values") or []
        for n, v in zip(full, values):
            if n not in linked:
                inputs[n] = v
        named = {k: v for k, v in (node.get("widgets_values_named") or {}).items() if k}
        stale = []
        for k, v in named.items():
            if k == "upload":
                continue
            root = k.split(".")[0]
            if root not in declared:
                continue  # control_after_generate и прочие поля только интерфейса
            if k in inputs:
                if inputs[k] != v:
                    stale.append(k)
                continue
            inputs[k] = v
        if stale and os.environ.get("SPRITE_DEBUG") == "1":
            print(f"[wf] #{node.get('id')} {cls}: widgets_values_named расходится "
                  f"с widgets_values ({', '.join(stale)}) — беру widgets_values")
        for i in node.get("inputs") or []:
            if i.get("link") is None:
                continue
            l = links.get(i["link"])
            if not l:
                warn.append(f"нода #{node.get('id')}: битая связь {i['link']}")
                continue
            inputs[i["name"]] = [str(l[1]), l[2]]
        graph[str(node["id"])] = {
            "class_type": cls,
            "inputs": inputs,
            "_meta": {"title": node.get("title") or cls},
        }
    return graph


def _node_by_class(graph: dict, cls: str) -> list[tuple[str, dict]]:
    return [(k, v) for k, v in graph.items() if v["class_type"] == cls]


def frames_for(seconds: float) -> int:
    """Кадров на выходе: 24 fps, длина = 17k + 5 (требование MiniMax H3)."""
    if not seconds or seconds <= 0:
        seconds = 5.0
    return snap_length(max(22, int(round(seconds * 24))))


def snap_length(frames: int) -> int:
    """Ближайшая допустимая длина вида 17k + 5."""
    k = max(1, int(round((max(5, int(frames)) - 5) / 17)))
    return 17 * k + 5


# --------------------------------------------------------------- манифесты

MODE_TITLES = {
    "walk": ("Ходьба (цикл)", "цикл шага, бесшовно повторяется"),
    "attack": ("Атака (действие)", "один удар: от стойки до возврата в стойку"),
}
SIZE_PRESETS = [(512, 512), (640, 512), (512, 640), (768, 768), (640, 640)]

# --------------------------------------------------------- промпт и цвет фона
# Цвет подложки — не «пожелание в тексте», а часть контракта: по нему работает
# SpriteChromaKey. Поэтому нужная фраза добавляется к промпту сама, откуда бы
# промпт ни пришёл.
COLOR_WORDS = ("magenta", "green", "blue")
COLOR_HEX = {"magenta": "#FF00FF", "green": "#00FF00", "blue": "#0000FF"}
BG_COLORS = r"magenta|green|blue|white|black|grey|gray|violet|purple|cyan|yellow|red|orange|pink"
TECH_TAIL = ("Crisp outlines and clear separate limbs, with no motion blur. "
             "No camera movement, zoom, rotation, character turning, sliding across the frame, "
             "extra limbs, extra fingers, morphing, text or new objects.")


def bg_clause(color: str) -> str:
    hexv = COLOR_HEX.get(color, color)
    return (f"The entire background is one flat, uniform solid {color} ({hexv}) "
            "with no gradients, no shadows, no ground and no other colors.")


def _force_bg_color(text: str, color: str) -> str:
    """Заменить цвет фона в промпте на выбранный, откуда бы промпт ни пришёл."""
    body = text or ""
    # «flat, uniform solid <color>» — фраза пресетов.
    body = re.sub(r"(?i)(\b(?:flat|uniform|solid)[^.!?]{0,30}?)\b(?:" + BG_COLORS + r")\b",
                  lambda m: m.group(1) + color, body)
    # «<color> background» / «<color> flat background».
    body = re.sub(r"(?i)\b(?:" + BG_COLORS + r")\b(\s+(?:flat\s+)?(?:background|backdrop)\b)",
                  lambda m: color + m.group(1), body)
    # «background is/stays/remains [a] [flat/plain/pure/dark] <color>».
    body = re.sub(
        r"(?i)(\b(?:background|backdrop)\s+"
        r"(?:is|stays|remains|should be|must be|will be|is a|is one)\s+"
        r"(?:a\s+)?(?:flat|uniform|solid|plain|pure|dark|light|bright|muted)?\s*)"
        r"\b(?:" + BG_COLORS + r")\b",
        lambda m: m.group(1) + color, body)
    # «transparent/no background» — модель не умеет прозрачность, нужен ровный ключ.
    body = re.sub(r"(?i)\b(?:a\s+|an\s+)?(?:transparent|no)\s+background\b",
                  lambda m: _bg_phrase(color, m.group(0)), body)
    return body


def _bg_phrase(color: str, src: str) -> str:
    """Фраза фона для случая «transparent/no background» с заглавной, если надо."""
    s = f"a flat, uniform solid {color} background"
    return s[0].upper() + s[1:] if src[:1].isupper() else s


# Кириллица → латиница: имя движения становится именем папки и zip.
_TRANSLIT = str.maketrans(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    "abvgdeejziyklmnoprstufhccss_y_eua",
)


def slugify(name: str, fallback: str) -> str:
    s = (name or "").strip().lower().translate(_TRANSLIT)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or fallback


def _bg_color_in(low: str) -> str:
    m = (re.search(r"\b(?:flat|uniform|solid)\b[^.]{0,40}?\b(magenta|green|blue)\b", low)
         or re.search(r"\b(magenta|green|blue)\b[^.]{0,40}?\bbackground\b", low))
    return m.group(1) if m else ""


def normalize_prompt(text: str, color: str) -> tuple[str, list[str], str]:
    """Дописать в промпт то, без чего конвейер не сработает.

    Возвращает (итоговый промпт, что дописано, предупреждение).
    """
    color = color if color in COLOR_WORDS else "magenta"
    body = (text or "").strip()
    body = _force_bg_color(body, color)
    low = body.lower()
    added: list[str] = []
    if not _bg_color_in(low):
        added.append(bg_clause(color))
    if "no motion blur" not in low:
        added.append(TECH_TAIL)
    final = " ".join([body] + added).strip()
    return final, added, ""


def load_workflows() -> list[dict]:
    out: list[dict] = []
    for path in sorted(WF_DIR.glob("*.json")):
        try:
            wf = json.loads(path.read_text("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[wf] {path.name}: {exc}")
            continue
        if "nodes" not in wf:
            continue
        nodes = wf["nodes"]
        h3 = next((n for n in nodes if n.get("type") == "MiniMaxH3ImageToVideo"), None)
        trim = next((n for n in nodes if n.get("type") == "SpriteLoopTrim"), None)
        if not h3 or not trim:
            continue
        named = h3.get("widgets_values_named") or {}
        vals = h3.get("widgets_values") or []
        # widgets_values — авторитетно; named только если позиционных нет.
        width = int(vals[1] if len(vals) > 1 else named.get("width") or 512)
        height = int(vals[2] if len(vals) > 2 else named.get("height") or 512)
        length = int(vals[3] if len(vals) > 3 else named.get("length") or 124)
        prompt = str(vals[0] if vals else named.get("prompt") or "")
        trim_vals = trim.get("widgets_values") or []
        trim_named = trim.get("widgets_values_named") or {}
        trim_mode = str(trim_vals[0] if trim_vals else trim_named.get("mode") or "cycle")
        mode = path.stem.lower()
        for key in MODE_TITLES:
            if key in mode:
                mode = key
                break
        title, hint = MODE_TITLES.get(mode, (path.stem, ""))
        out.append({
            "id": path.stem,
            "mode": mode,
            "title": title,
            "hint": hint,
            "file": path.name,
            "width": width,
            "height": height,
            "length": length,
            "prompt": prompt,
            "trim_mode": trim_mode,
            # Человеческое имя технической разницы: как результат повторяется.
            "repeat": "once" if trim_mode == "action" else "cycle",
            "nodes": len(nodes),
        })
    order = {name: i for i, name in enumerate(MODE_TITLES)}
    out.sort(key=lambda m: order.get(m["mode"], 99))
    return out


def find_workflow(mode: str):
    """Режим (walk/attack/cycle/once) → (путь к файлу, манифест)."""
    for m in load_workflows():
        if mode in (m["mode"], m["id"], m["repeat"]):
            return WF_DIR / m["file"], m
    return None, None


# ------------------------------------------------------------------- сборка

def build_graph(manifest: dict, params: dict, info: dict, run: str) -> tuple[dict, dict]:
    """Собрать API-граф под прогон.

    Возвращает (граф, сведения): сведения = warnings, prompt, prompt_added.
    """
    warn: list[str] = []
    wf = json.loads((WF_DIR / manifest["file"]).read_text("utf-8"))
    graph = ui_to_api(wf, info, warn)

    width = int(params.get("width") or manifest["width"])
    height = int(params.get("height") or manifest["height"])
    width, height = width - width % 32, height - height % 32
    seconds = float(params.get("seconds") or 0) or (manifest["length"] / 24)
    length = snap_length(int(params.get("length") or 0) or frames_for(seconds))
    seed = int(params.get("seed") or 0) or random.randrange(1, 2**50)
    steps = int(params.get("steps") or 20)
    adv = params.get("advanced") or {}

    # Сначала ключ вырезания: от него зависит формулировка про фон в промпте.
    key_color = str(adv.get("key_color") or "magenta")
    if key_color not in COLOR_WORDS:
        key_color = "magenta"
    for _, n in _node_by_class(graph, "SpriteChromaKey"):
        for key, default in (("key_color", "magenta"), ("clip_black", 0.04),
                             ("clip_white", 0.97), ("despill", 1.0),
                             ("choke_px", 0.0), ("edge_bleed_px", 4)):
            if key in n["inputs"] and adv.get(key) not in (None, ""):
                n["inputs"][key] = adv[key]
        key_color = str(n["inputs"].get("key_color") or key_color)

    prompt, added, conflict = normalize_prompt(
        str(params.get("prompt") or manifest["prompt"]), key_color)
    if conflict:
        warn.append(conflict)
    for _, n in _node_by_class(graph, "MiniMaxH3ImageToVideo"):
        n["inputs"]["prompt"] = prompt
        n["inputs"]["width"] = width
        n["inputs"]["height"] = height
        n["inputs"]["length"] = length
    for _, n in _node_by_class(graph, "RandomNoise"):
        n["inputs"]["noise_seed"] = seed
    for _, n in _node_by_class(graph, "BasicScheduler"):
        n["inputs"]["steps"] = steps
    for _, n in _node_by_class(graph, "SpriteLoopTrim"):
        if adv.get("max_frames") not in (None, ""):
            n["inputs"]["max_frames"] = int(adv["max_frames"])
        if adv.get("dedupe_twos") is not None:
            n["inputs"]["dedupe_twos"] = bool(adv["dedupe_twos"])
        if adv.get("keep_all"):
            n["inputs"]["mode"] = "keep"       # все кадры, без поиска цикла
        n["inputs"].setdefault("min_frames", 12)

    # Своя папка на прогон: ComfyUI не перезапишет прошлые результаты.
    slug = slugify(params.get("name"), manifest["repeat"])
    for node_id, n in graph.items():
        if n["class_type"] == "SaveVideo":
            n["inputs"]["filename_prefix"] = f"SpriteAnim/{slug}/{run}/preview"
        elif n["class_type"] == "SaveImage":
            tail = "rgba/frame" if "/rgba/" in str(n["inputs"].get("filename_prefix", "")) else "frames/frame"
            n["inputs"]["filename_prefix"] = f"SpriteAnim/{slug}/{run}/{tail}"
    return graph, {"warnings": warn, "prompt": prompt, "prompt_added": added,
                   "key_color": key_color, "slug": slug}


def _run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


# ------------------------------------------------------------------- статус

def _history_meta(entry: dict) -> dict:
    """Параметры прогона из истории ComfyUI — чтобы результат можно было открыть снова."""
    pr = entry.get("prompt") or []
    graph = pr[2] if isinstance(pr, (list, tuple)) and len(pr) > 2 and isinstance(pr[2], dict) else {}
    meta: dict = {"seed": None, "slug": "", "prompt": ""}
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        cls, inp = node.get("class_type"), node.get("inputs") or {}
        if cls == "MiniMaxH3ImageToVideo":
            for k in ("width", "height", "length", "prompt"):
                if k in inp:
                    meta[k] = inp[k]
        elif cls == "RandomNoise" and inp.get("noise_seed") is not None:
            meta["seed"] = inp["noise_seed"]
        elif cls == "SaveVideo":
            parts = str(inp.get("filename_prefix") or "").split("/")
            if len(parts) >= 3 and parts[0] == "SpriteAnim":
                meta["slug"] = parts[1]
    return meta


def output_location(subfolder: str) -> tuple[str, str, list[str]]:
    """Куда в output/ положить файл: (группа, прогон, хвост подпапок).

    SpriteAnim/img/<run>  → images/<run>
    SpriteAnim/bg/<run>   → background/<run>
    SpriteAnim/walk/<run> → animation/walk/<run>
    SpriteAnim/up/<run>   → upscaled/<run>
    """
    parts = [p for p in str(subfolder or "").replace("\\", "/").split("/") if p]
    if len(parts) >= 3 and parts[0] == "SpriteAnim":
        kind, run, tail = parts[1], parts[2], parts[3:]
        if kind == "img":
            return "images", run, tail
        if kind == "bg":
            return "background", run, tail
        if kind == "up":
            return "upscaled", run, tail
        return f"animation/{kind}", run, tail
    return "other", time.strftime("%Y%m%d-%H%M%S"), []


_collect_lock = threading.Lock()


def collect_outputs(st: dict) -> dict:
    """Копирует результаты прогона из ComfyUI в свою папку output/."""
    outs = [o for o in (st.get("outputs") or []) if o.get("filename")]
    if not outs:
        return {}
    dirs: dict[str, int] = {}
    with _collect_lock:
        for o in outs:
            group, run, tail = output_location(o.get("subfolder") or "")
            target = output_dir() / group / run
            if tail:
                target = target.joinpath(*tail)
            path = target / o["filename"]
            try:
                if not path.is_file() or path.stat().st_size == 0:
                    params = urllib.parse.urlencode({
                        "filename": o["filename"],
                        "subfolder": o.get("subfolder") or "",
                        "type": o.get("type") or "output",
                    })
                    with urllib.request.urlopen(COMFY + "/view?" + params, timeout=180) as r:
                        data = r.read()
                    target.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                dirs[str(target)] = dirs.get(str(target), 0) + 1
            except Exception:  # noqa: BLE001
                continue
    return {"dirs": list(dirs.keys()), "files": sum(dirs.values())}


# ------------------------------------------------------------------- апскейл
# Кадры анимации увеличиваются по одному промпту: так видеопамять занята
# ровно одним кадром, а прогресс виден на каждом шаге.
UPSCALE_MODEL = "RealESRGAN_x4plus_anime_6B.pth"
_UPSCALE_CANCEL: dict[str, threading.Event] = {}
_UPSCALE_LOCK = threading.Lock()


def upscale_model_available() -> str:
    """Имя загружаемой модели апскейла или ''."""
    for force in (False, True):
        try:
            opts = _choices(object_info(force=force), "UpscaleModelLoader", "model_name")
        except Exception:  # noqa: BLE001
            return ""
        if UPSCALE_MODEL in opts:
            return UPSCALE_MODEL
        found = next((o for o in opts if "esrgan" in o.lower()), "")
        if found:
            return found
    return ""


def _png_has_alpha(path: Path) -> bool:
    """PNG с альфой (color type 4/6) — без зависимостей, по заголовку IHDR."""
    try:
        with path.open("rb") as f:
            head = f.read(26)
    except OSError:
        return False
    return head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 26 and head[25] in (4, 6)


def upscale_frames(src: str) -> tuple[Path, list[Path]]:
    """Папка с кадрами внутри output/ и список frame_*.png."""
    base = output_dir().resolve()
    p = Path(src)
    if not p.is_absolute():
        p = base / src
    try:
        p = p.resolve()
        p.relative_to(base)
    except (OSError, ValueError) as exc:
        raise ValueError("папка с кадрами должна лежать внутри output") from exc
    if not p.is_dir():
        raise ValueError("папка с кадрами не найдена")
    folder = p / "rgba" if (p / "rgba").is_dir() else p
    files = sorted(folder.glob("frame_*.png"))
    if not files:
        raise ValueError("в папке нет кадров frame_*.png")
    if not _png_has_alpha(files[0]):
        raise ValueError("кадры без прозрачности — нужны RGBA-кадры из анимации")
    return folder, files


def _output_rel(path: Path) -> str:
    """Путь файла/папки относительно output/ в виде слэшей."""
    return path.resolve().relative_to(output_dir().resolve()).as_posix()


def upscale_sources(limit: int = 12) -> list[dict]:
    """Готовые прогоны анимации с кадрами: свежие сверху."""
    root = output_dir() / "animation"
    if not root.is_dir():
        return []
    out = []
    for run in root.glob("*/*"):
        if not run.is_dir():
            continue
        folder = run / "rgba" if (run / "rgba").is_dir() else run
        files = sorted(p.name for p in folder.glob("frame_*.png"))
        if not files:
            continue
        if not _png_has_alpha(folder / files[0]):
            continue
        out.append({"dir": str(folder.resolve()), "rel": _output_rel(folder),
                    "name": run.parent.name, "run": run.name,
                    "count": len(files), "files": files[:400],
                    "ts": folder.stat().st_mtime})
    out.sort(key=lambda s: s["ts"], reverse=True)
    return out[:limit]


def output_file(rel: str) -> tuple[bytes, str]:
    """Файл из output/ для превью во вкладке «Апскейл»."""
    base = output_dir().resolve()
    p = (base / (rel or "")).resolve()
    try:
        p.relative_to(base)
    except ValueError as exc:
        raise ValueError("файл должен лежать внутри output") from exc
    if not p.is_file():
        raise ValueError("файл не найден")
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return p.read_bytes(), ctype


def _upscale_set(job_id: str, **kw) -> None:
    with _jobs_lock:
        data = jobs_load()
        entry = data.get(job_id)
        if not entry:
            return
        entry.update(kw)
        jobs_save(data)


def upscale_recover() -> int:
    """Незавершённый апскейл после перезапуска продолжить нельзя — помечаем ошибкой."""
    count = 0
    with _jobs_lock:
        data = jobs_load()
        for entry in data.values():
            if entry.get("kind") == "upscale" and entry.get("state") in ("queued", "running"):
                entry["state"] = "error"
                entry["error"] = "прервано перезапуском приложения"
                count += 1
        if count:
            jobs_save(data)
    return count


def _png_size(path: Path) -> tuple[int, int]:
    """Ширина и высота PNG из заголовка IHDR."""
    try:
        with path.open("rb") as f:
            head = f.read(24)
    except OSError:
        return 0, 0
    if head[:8] != b"\x89PNG\r\n\x1a\n" or len(head) < 24:
        return 0, 0
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _upscale_graph(uploaded: str, model: str, factor: int, run: str) -> dict:
    # LoadImage в этой версии ComfyUI отдаёт RGB и отдельную маску прозрачности,
    # поэтому альфу возвращаем узлом JoinImageWithAlpha (он же её растягивает).
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": uploaded, "upload": "image"}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
        "3": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
    }
    last = "3"
    if factor < 4:
        graph["4"] = {"class_type": "ImageScaleBy",
                      "inputs": {"image": ["3", 0], "upscale_method": "lanczos",
                                 "scale_by": factor / 4.0}}
        last = "4"
    graph["5"] = {"class_type": "JoinImageWithAlpha",
                  "inputs": {"image": [last, 0], "alpha": ["1", 1]}}
    graph["6"] = {"class_type": "SaveImage",
                  "inputs": {"images": ["5", 0],
                             "filename_prefix": f"SpriteAnim/up/{run}/rgba/frame"}}
    return graph


def upscale_start(body: dict) -> dict:
    stop_agent_for_memory()
    folder, files = upscale_frames(str(body.get("dir") or ""))
    try:
        factor = int(body.get("factor") or 2)
    except (TypeError, ValueError):
        factor = 2
    factor = max(2, min(4, factor))
    model = upscale_model_available()
    if not model:
        raise RuntimeError("модель апскейла не установлена — скачайте её в настройках")
    if folder.name == "rgba":
        base = folder.parent.parent
    else:
        base = folder.parent
    if folder.name == "rgba":
        base = folder.parent.parent
        src_run = folder.parent.name
    else:
        base = folder.parent
        src_run = folder.name
    name = base.name or folder.name
    run = _run_id()
    job_id = "up-" + uuid.uuid4().hex[:12]
    src = {"dir": str(folder), "rel": _output_rel(folder), "name": name, "run": src_run}
    jobs_add({"id": job_id, "kind": "upscale", "state": "queued", "done": 0,
              "total": len(files), "ts": time.time(), "name": name, "factor": factor,
              "run": run, "src": str(folder), "outputs": [],
              "local": {"dirs": [], "files": 0}})
    event = threading.Event()
    with _UPSCALE_LOCK:
        _UPSCALE_CANCEL[job_id] = event
    threading.Thread(target=_upscale_worker,
                     args=(job_id, files, factor, model, run, event, src),
                     daemon=True).start()
    return {"id": job_id, "total": len(files), "factor": factor, "run": run, "name": name}


def _upscale_worker(job_id: str, files: list[Path], factor: int,
                    model: str, run: str, event: threading.Event, src: dict) -> None:
    outs: list[dict] = []

    def stop(state: str, error: str = "") -> None:
        local = collect_outputs({"outputs": outs}) if outs else {"dirs": [], "files": 0}
        if state == "done" and local.get("dirs"):
            _upscale_meta(Path(local["dirs"][0]), run, factor, outs, src)
        _upscale_set(job_id, state=state, error=error, done=len(outs),
                     outputs=outs, local=local)

    try:
        for i, path in enumerate(files, 1):
            if event.is_set():
                return stop("error", "остановлено")
            blob = path.read_bytes()
            uploaded = upload_image(f"up_{run}_{i:05d}.png", blob)
            graph = _upscale_graph(uploaded, model, factor, run)
            res = comfy_json("/prompt", {"prompt": graph, "client_id": uuid.uuid4().hex,
                                         "extra_data": {"preview_method": "latent2rgb"}},
                             timeout=60)
            pid = str(res.get("prompt_id") or "")
            if res.get("error") or not pid:
                raise RuntimeError(str(res.get("error") or "ComfyUI не принял задание"))
            deadline = time.time() + 300
            entry = None
            while time.time() < deadline:
                if event.is_set():
                    try:
                        comfy_json("/interrupt", {}, timeout=10)
                    except Exception:  # noqa: BLE001
                        pass
                    return stop("error", "остановлено")
                hist = comfy_json(f"/history/{pid}", timeout=10)
                if isinstance(hist, dict) and pid in hist:
                    entry = hist[pid]
                    break
                time.sleep(1.0)
            if entry is None:
                raise RuntimeError(f"кадр {i} не обработался за 5 минут")
            status = entry.get("status") or {}
            if status.get("status_str", "success") != "success" or status.get("error"):
                err = ""
                for m in status.get("messages") or []:
                    if isinstance(m, list) and m and m[0] in ("execution_error", "execution_interrupted"):
                        err = str((m[1] or {}).get("exception_message") or m[0])
                raise RuntimeError(err or "ошибка апскейла")
            for node_out in (entry.get("outputs") or {}).values():
                for item in node_out.get("images") or []:
                    if isinstance(item, dict) and item.get("filename"):
                        outs.append({"kind": "image", "filename": item["filename"],
                                     "subfolder": item.get("subfolder", ""),
                                     "type": item.get("type", "output")})
            _upscale_set(job_id, state="running", done=len(outs),
                         outputs=list(outs), total=len(files))
        stop("done")
    except Exception as exc:  # noqa: BLE001
        stop("error", f"{type(exc).__name__}: {exc}")
    finally:
        with _UPSCALE_LOCK:
            _UPSCALE_CANCEL.pop(job_id, None)


def _upscale_meta(folder: Path, run: str, factor: int, outs: list[dict], src: dict) -> None:
    """meta.json рядом с увеличенными кадрами: связь «анимация → апскейл»."""
    files = [o["filename"] for o in outs if o.get("filename")]
    width = height = 0
    if files:
        width, height = _png_size(folder / files[0])
    meta = {"run": run, "factor": factor, "count": len(files),
            "width": width, "height": height, "files": files,
            "source": src, "ts": time.time()}
    try:
        (folder.parent / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    except OSError:
        pass


def upscale_results(limit: int = 40) -> list[dict]:
    """Готовые апскейлы: свежие сверху, с привязкой к исходному прогону."""
    root = output_dir() / "upscaled"
    if not root.is_dir():
        return []
    out = []
    for meta in root.glob("*/meta.json"):
        try:
            data = json.loads(meta.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        run_dir = meta.parent
        files = [str(n) for n in (data.get("files") or [])]
        if not files:
            continue
        frames = run_dir / "rgba" if (run_dir / "rgba").is_dir() else run_dir
        out.append({**data, "dir": str(run_dir.resolve()),
                    "rel": _output_rel(frames), "files": files})
    out.sort(key=lambda r: float(r.get("ts") or 0), reverse=True)
    return out[:limit]


def sheets_list(limit: int = 20) -> list[dict]:
    """Сохранённые листы из output/sheets: свежие сверху."""
    root = sheets_dir()
    if not root.is_dir():
        return []
    out = []
    for js in root.glob("*/*-sheet.json"):
        try:
            data = json.loads(js.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        dest = js.parent
        png = dest / str(data.get("image") or "")
        if not png.is_file():
            found = sorted(dest.glob("*.png"))
            png = found[0] if found else None
        preview = dest / "preview.png"
        out.append({
            "dir": str(dest.resolve()), "name": dest.name,
            "rel_dir": _output_rel(dest),
            "image": png.name if png else "",
            "rel": _output_rel(png) if png else "",
            "preview": _output_rel(preview) if preview.is_file() else "",
            "columns": data.get("columns") or 0,
            "rows": data.get("rows") or 0,
            "count": data.get("count") or 0,
            "frame": data.get("frame") or {},
            "origin": data.get("origin") or {},
            "ts": dest.stat().st_mtime,
        })
    out.sort(key=lambda s: s["ts"], reverse=True)
    return out[:limit]


def save_sheet_preview(dir_raw: str, blob: bytes) -> dict:
    """Кладёт маленькое превью к уже сохранённому листу."""
    base = sheets_dir().resolve()
    p = Path(str(dir_raw or ""))
    if not p.is_absolute():
        p = base / p
    p = p.resolve()
    try:
        p.relative_to(base)
    except ValueError as exc:
        raise ValueError("папка листа должна лежать в output/sheets") from exc
    if not p.is_dir():
        raise ValueError("папка листа не найдена")
    if not blob or len(blob) < 100:
        raise ValueError("пустое превью")
    (p / "preview.png").write_bytes(blob)
    return {"ok": True, "file": str(p / "preview.png")}


# ---------------------------------------------- установка ComfyUI и моделей
# Каталог того, что нужно приложению. Размеры — реальные (байты), источники —
# репозитории Hugging Face, пути внутри них проверены.

MODEL_GROUPS = [
    {
        "id": "qwen",
        "title": "Qwen Image 2.1",
        "what": "Генерация картинок и удаление фона",
        "note": "Основная модель для вкладок «Картинка» и «Убрать фон». "
                "Скачиваются диффузионная модель (int8), текстовый инкодер Qwen3-VL 8B и VAE.",
        "repo": "Comfy-Org/Qwen-Image-2.1",
        "enabled": True,
        "files": [
            {"target": "comfy", "folder": "diffusion_models",
             "name": "qwen_image_2.1_int8_convrot.safetensors",
             "path": "diffusion_models/qwen_image_2.1_int8_convrot.safetensors",
             "size": 7256783064, "what": "диффузионная модель, int8"},
            {"target": "comfy", "folder": "text_encoders",
             "name": "qwen3vl_8b_int8_convrot.safetensors",
             "path": "text_encoders/qwen3vl_8b_int8_convrot.safetensors",
             "size": 9350798360, "what": "текстовый инкодер Qwen3-VL 8B"},
            {"target": "comfy", "folder": "vae",
             "name": "qwen_image_2.1_vae_bf16.safetensors",
             "path": "vae/qwen_image_2.1_vae_bf16.safetensors",
             "size": 675509688, "what": "VAE"},
        ],
    },
    {
        "id": "anim",
        "title": "MiniMax H3 — анимация",
        "what": "Спрайтовые анимации (ходьба, атака)",
        "note": "Модель для вкладки «Анимация». Скачиваются видео-модель, "
                "текстовый инкодер Qwen3-VL 32B и видео-VAE.",
        "repo": "Comfy-Org/MiniMax-H3",
        "enabled": True,
        "files": [
            {"target": "comfy", "folder": "diffusion_models",
             "name": "minimax_h3_fl2va_pruned_w6a8.safetensors",
             "path": "diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors",
             "size": 15983746636, "what": "видео-модель MiniMax H3"},
            {"target": "comfy", "folder": "text_encoders",
             "name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
             "path": "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
             "size": 15687142551, "what": "текстовый инкодер Qwen3-VL 32B"},
            {"target": "comfy", "folder": "vae",
             "name": "minimax_h3_video_vae_int8_convrot.safetensors",
             "path": "vae/minimax_h3_video_vae_int8_convrot.safetensors",
             "size": 2811065184, "what": "видео-VAE"},
        ],
    },
    {
        "id": "agent",
        "title": "Агент (Gemma 4 12B)",
        "what": "Пишет промпты и видит картинки",
        "note": "Локальный агент для кнопки «Промпт агентом»: модель Gemma 4 12B "
                "(Q4_0), визуальный проектор и сборка llama.cpp. Работает без интернета.",
        "repo": "unsloth/gemma-4-12b-it-GGUF",
        "enabled": True,
        "files": [
            {"target": "agent", "name": "gemma-4-12b-it-Q4_0.gguf",
             "path": "gemma-4-12b-it-Q4_0.gguf", "repo": "unsloth/gemma-4-12b-it-GGUF",
             "size": 6738475840, "what": "модель агента, Q4_0"},
            {"target": "agent", "name": "mmproj-F16.gguf",
             "path": "mmproj-F16.gguf", "repo": "unsloth/gemma-4-12b-it-GGUF",
             "size": 175115840, "what": "визуальный проектор — агент видит картинки"},
        ],
    },
    {
        "id": "upscale",
        "title": "Апскейл (Real-ESRGAN anime)",
        "what": "Увеличение кадров перед спрайт-листом",
        "note": "Модель для вкладки «Апскейл»: увеличивает кадры с прозрачностью в 2–4 раза "
                "перед сборкой листа. 17 МБ, считает на видеокарте.",
        "repo": "ximso/RealESRGAN_x4plus_anime_6B",
        "enabled": True,
        "files": [
            {"target": "comfy", "folder": "upscale_models",
             "name": "RealESRGAN_x4plus_anime_6B.pth",
             "path": "RealESRGAN_x4plus_anime_6B.pth",
             "size": 17938799, "what": "модель апскейла, 4×"},
        ],
    },
]


# ------------------------------------------------------- голосовой ввод
# GigaAM v3 (MIT) + transcribe.cpp (MIT). Движок — набор DLL, модель — GGUF.
VOICE_DIR = ROOT / "voice"
VOICE_LIB = VOICE_DIR / "lib"
VOICE_MODELS = VOICE_DIR / "models"
VOICE_PY = DATA / "voice" / "py"
VOICE_ENGINE_URL = ("https://github.com/handy-computer/transcribe.cpp/releases/download/"
                    "v0.4.2/transcribe-native-0.4.2-windows-x86_64-cpu-vulkan.tar.gz")
VOICE_ENGINE_SIZE = 18_100_000
VOICE_MODEL_NAME = "gigaam-v3-e2e-rnnt-Q8_0.gguf"


def voice_engine_path() -> Path | None:
    for name in ("transcribe.dll", "libtranscribe.dll"):
        p = VOICE_LIB / name
        if p.is_file():
            return p
    return None


def voice_model_path() -> Path | None:
    if not VOICE_MODELS.is_dir():
        return None
    candidates = sorted(VOICE_MODELS.glob("*.gguf"))
    for p in candidates:
        if "gigaam" in p.name.lower() or "asr" in p.name.lower():
            return p
    return candidates[0] if candidates else None


def voice_binding_ok() -> bool:
    return (VOICE_PY / "transcribe_cpp" / "__init__.py").is_file()


def voice_ready() -> bool:
    return bool(voice_engine_path() and voice_model_path() and voice_binding_ok())


MODEL_GROUPS.append({
    "id": "voice",
    "title": "Голосовой ввод (GigaAM v3)",
    "what": "Распознавание речи для промптов",
    "note": "Необязательно: без него кнопки микрофона нет. Русская модель GigaAM v3 (MIT) "
            "и движок transcribe.cpp (MIT) работают локально — звук никуда не отправляется.",
    "repo": "handy-computer/gigaam-v3-e2e-rnnt-gguf",
    "enabled": True,
    "files": [
        {"target": "voice_engine", "name": "transcribe.cpp (движок)",
         "url": VOICE_ENGINE_URL, "size": VOICE_ENGINE_SIZE,
         "what": "распаковка в voice/lib (Windows, CPU+Vulkan)"},
        {"target": "voice_model", "name": VOICE_MODEL_NAME,
         "path": "gigaam-v3-e2e-rnnt-Q8_0.gguf",
         "size": 273_724_832, "what": "русская модель распознавания, Q8_0"},
    ],
})

COMFY_SITE = "https://www.comfy.org/download"
COMFY_PORTABLE_RE = r"ComfyUI_windows_portable_nvidia(?:_.*)?\.7z$"


def gb(num: float) -> float:
    return round(float(num or 0) / (1024 ** 3), 2)


def fmt_size(num: float) -> str:
    num = float(num or 0)
    if num >= 1024 ** 3:
        return f"{num / 1024 ** 3:.1f} ГБ"
    if num >= 1024 ** 2:
        return f"{num / 1024 ** 2:.0f} МБ"
    return f"{num / 1024:.0f} КБ"


_agent_home_cache: list = []


def agent_home() -> Path:
    """Где живут модель агента и llama.cpp (можно задать в настройках)."""
    if _agent_home_cache:
        return _agent_home_cache[0]
    raw = _settings.get("agent_dir") or os.environ.get("SPRITE_AGENT_DIR")
    if raw:
        home = Path(raw)
    else:
        legacy = Path("E:/ComfyModelsHub/models/MinimaxH3_assistant")
        home = legacy if legacy.is_dir() else (ROOT / "models" / "agent")
    _agent_home_cache.append(home)
    return home


def agent_models_dir() -> Path:
    return agent_home() / "models"


def agent_llama_dir() -> Path:
    return agent_home() / "llama.cpp"


def _first(paths, patterns) -> Path | None:
    for pattern in patterns:
        for p in paths.glob(pattern):
            if p.is_file():
                return p
    return None


def agent_model_path() -> Path:
    direct = agent_models_dir() / "gemma-4-12B-it-Q4_0.gguf"
    if direct.is_file():
        return direct
    found = _first(agent_models_dir(), ["*gemma*Q4_0*.gguf", "*gemma*.gguf"])
    return found or direct


def agent_mmproj_path() -> Path:
    direct = agent_models_dir() / "mmproj-gemma-4-12B-it-Q8_0.gguf"
    if direct.is_file():
        return direct
    found = _first(agent_models_dir(), ["mmproj*.gguf", "*mmproj*.gguf"])
    return found or direct


def agent_server_path() -> Path | None:
    for name in ("llama-server.exe", "llama-server"):
        p = agent_llama_dir() / name
        if p.is_file():
            return p
    found = _first(agent_llama_dir(), ["**/llama-server.exe", "**/llama-server"])
    return found


_folder_paths_cache: dict = {}
_folder_paths_t: float = 0.0


def comfy_folder_paths(force: bool = False) -> dict:
    global _folder_paths_t
    if not force and _folder_paths_t:
        ttl = 300.0 if _folder_paths_cache else 10.0
        if time.time() - _folder_paths_t < ttl:
            return _folder_paths_cache
    try:
        data = comfy_json("/internal/folder_paths", timeout=10)
        if isinstance(data, dict):
            _folder_paths_cache.clear()
            _folder_paths_cache.update(data)
    except Exception:  # noqa: BLE001
        pass
    _folder_paths_t = time.time()
    return _folder_paths_cache


def find_model_file(folder: str, name: str) -> Path | None:
    roots = []
    custom = (_settings.get("models_dir") or "").strip()
    if custom:
        roots.append(custom)
    roots += list(comfy_folder_paths().get(folder, []) or [])
    for root in roots:
        p = Path(root) / name
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def _file_status(item: dict) -> dict:
    out = {k: item[k] for k in ("name", "what", "size") if k in item}
    out["folder"] = item.get("folder", "")
    target = item.get("target")
    if target == "agent":
        found = None
        want = item["name"].lower()
        for p in agent_models_dir().glob("*.gguf"):
            if p.name.lower() == want:
                found = p
                break
        if found is None and item["name"].lower().startswith("gemma"):
            found = agent_model_path() if agent_model_path().is_file() else None
        if found is None and "mmproj" in want:
            found = agent_mmproj_path() if agent_mmproj_path().is_file() else None
    elif target == "voice_engine":
        found = voice_engine_path()
    elif target == "voice_model":
        found = voice_model_path()
        if found is not None and found.stat().st_size < 50 * 1024 * 1024:
            found = None
    else:
        found = find_model_file(item.get("folder", ""), item["name"])
    out["present"] = bool(found)
    out["found_path"] = str(found) if found else ""
    out["found_size"] = found.stat().st_size if found else 0
    if not found:
        if target == "agent":
            out["target_dir"] = str(agent_models_dir())
        elif target == "voice_engine":
            out["target_dir"] = str(VOICE_LIB)
        elif target == "voice_model":
            out["target_dir"] = str(VOICE_MODELS)
        else:
            try:
                out["target_dir"] = str(_comfy_target(item.get("folder", ""), item["name"]).parent)
            except Exception:  # noqa: BLE001
                out["target_dir"] = ""
    return out


def model_group_info(group: dict) -> dict:
    files = [_file_status(f) for f in group["files"]]
    have = [f for f in files if f["present"]]
    total = sum(f["size"] for f in files)
    done = sum(f["found_size"] or f["size"] for f in files if f["present"])
    if len(have) == len(files):
        state = "ok"
    elif have:
        state = "partial"
    else:
        state = "missing"
    if group["id"] == "agent":
        llama = agent_server_path()
        files.append({
            "name": "llama.cpp (llama-server)", "what": "движок для агента",
            "folder": "", "size": 0, "present": bool(llama),
            "found_path": str(llama) if llama else "", "found_size": 0,
            "size_hint": "≈ 0,3 ГБ",
        })
        if not llama and state == "ok":
            state = "partial"
    if group["id"] == "agent":
        target = str(agent_home())
    elif group["id"] == "voice":
        target = str(VOICE_DIR)
    else:
        target = models_dir()
    return {
        "id": group["id"], "title": group["title"], "what": group["what"],
        "note": group["note"], "state": state, "enabled": group.get("enabled", True),
        "size": total, "size_text": fmt_size(total), "done": done,
        "target": target,
        "files": files,
    }


def setup_status() -> dict:
    online = False
    version = ""
    try:
        st = comfy_json("/system_stats", timeout=6)
        online = True
        version = str(((st or {}).get("system") or {}).get("comfyui_version") or "")
    except Exception:  # noqa: BLE001
        online = False
    roots = comfy_folder_paths(force=online)
    first_root = next((r for r in (roots.get("diffusion_models") or []) if r), "")
    models_root = models_dir() or (str(Path(first_root).parent) if first_root else "")
    groups = [model_group_info(g) for g in MODEL_GROUPS]
    return {
        "comfy": {
            "online": online,
            "version": version,
            "url": COMFY,
            "site": COMFY_SITE,
            "dir": str(ROOT / "ComfyUI"),
            "portable": (ROOT / "ComfyUI" / "ComfyUI_windows_portable").is_dir(),
            "cmd": comfy_launcher_path(),
            "remembered": bool(_settings.get("comfy_cmdline")),
            "owned": comfy_owned()["owned"],
            "auto": bool(_settings.get("comfy_auto")),
        },
        "models_root": models_root,
        "agent_dir": str(agent_home()),
        "groups": groups,
        "total_size": sum(g["size"] for g in groups if g.get("enabled")),
        "install": setup_progress(),
    }


# ---------------------------------------------------------------- загрузки
_progress: dict = {
    "active": False, "kind": "", "group": "", "file": "", "done": 0, "total": 0,
    "speed": 0.0, "message": "", "error": "", "phase": "",
}
_progress_lock = threading.Lock()
_cancel_flag = threading.Event()


def setup_progress() -> dict:
    with _progress_lock:
        return dict(_progress)


def _set_progress(**kw) -> None:
    with _progress_lock:
        _progress.update(kw)


def _http_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SpriteAnimStudio/0.1"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return int(r.headers.get("Content-Length") or 0)


def _download(url: str, dest: Path, group: str = "", name: str = "") -> Path:
    """Скачать файл с прогрессом, докачкой и повторами при обрывах."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    total = 0
    try:
        total = _http_size(url) or 0
    except Exception:  # noqa: BLE001 — HEAD не обязателен, размер придёт из GET
        total = 0
    last_error: Exception | None = None
    for attempt in range(1, 7):
        try:
            done = part.stat().st_size if part.is_file() else 0
            if total and done >= total:
                if dest.exists():
                    dest.unlink()
                part.replace(dest)
                return dest
            headers = {"User-Agent": "SpriteAnimStudio/0.1",
                       "Accept": "*/*", "Accept-Encoding": "identity", "Connection": "close",
                       "Range": f"bytes={done}-"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                if done and r.status != 206:
                    done = 0
                    part.unlink(missing_ok=True)
                if not total:
                    total = int(r.headers.get("Content-Length") or 0) + done
                _set_progress(group=group, file=name, done=done, total=total,
                              message=f"скачивание, попытка {attempt}" if attempt > 1 else "")
                last = time.time()
                chunk_start = done
                with part.open("ab") as fh:
                    while True:
                        if _cancel_flag.is_set():
                            raise RuntimeError("скачивание отменено")
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if now - last >= 0.4:
                            speed = (done - chunk_start) / max(now - last, 0.001)
                            _set_progress(done=done, speed=speed)
                            last, chunk_start = now, done
            done = part.stat().st_size if part.is_file() else 0
            _set_progress(done=done, total=total or done, speed=0.0)
            if total and done < total:
                raise IOError(f"скачано {done} из {total} байт")
            if dest.exists():
                dest.unlink()
            part.replace(dest)
            return dest
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001 — обрыв сети: пробуем ещё раз
            last_error = exc
            if _cancel_flag.is_set():
                raise RuntimeError("скачивание отменено") from exc
            print(f"[setup] {name or dest.name}: попытка {attempt} — {type(exc).__name__}: {exc}")
            _set_progress(message=f"обрыв связи, повтор {attempt}/3")
            time.sleep(1.5)
    raise RuntimeError(f"не удалось скачать {name or dest.name}: {last_error}")


def _comfy_target(folder: str, name: str) -> Path:
    custom = (_settings.get("models_dir") or "").strip()
    if custom:
        return Path(custom) / folder / name
    roots = comfy_folder_paths().get(folder) or []
    root = next((r for r in roots if r), "")
    if not root:
        raise RuntimeError("ComfyUI не запущен — укажите папку моделей в настройках")
    return Path(root) / name


def _download_file(item: dict, group: dict) -> Path:
    target = item.get("target", "comfy")
    _set_progress(file=item["name"], message=item.get("what", ""))
    if target == "voice_engine":
        dest = VOICE_DIR / "download" / "transcribe-engine.tar.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _download(item["url"], dest, group=group["id"], name=item["name"])
        _set_progress(phase="extract", message="распаковываю движок", done=0, total=0)
        VOICE_LIB.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xzf", str(dest), "-C", str(VOICE_LIB)], check=True,
                       creationflags=0x08000000 if os.name == "nt" else 0)
        # архив кладёт файлы в подпапку — поднимаем их наверх
        subs = [p for p in VOICE_LIB.iterdir() if p.is_dir()]
        if subs and not (VOICE_LIB / "transcribe.dll").is_file():
            inner = subs[0]
            for p in list(inner.iterdir()):
                shutil.move(str(p), str(VOICE_LIB / p.name))
            try:
                inner.rmdir()
            except OSError:
                pass
        dest.unlink(missing_ok=True)
        return VOICE_LIB / "transcribe.dll"
    if target == "voice_model":
        dest = VOICE_MODELS / item["name"]
        url = f"https://huggingface.co/{group['repo']}/resolve/main/{item['path']}"
        return _download(url, dest, group=group["id"], name=item["name"])
    if target == "agent":
        dest = agent_models_dir() / item["name"]
        url = f"https://huggingface.co/{group['repo']}/resolve/main/{item['path']}"
    else:
        dest = _comfy_target(item.get("folder", ""), item["name"])
        url = f"https://huggingface.co/{group['repo']}/resolve/main/{item['path']}"
    return _download(url, dest, group=group["id"], name=item["name"])


_voice_lock = threading.Lock()
_voice_state: dict = {"loaded": False, "error": ""}


def voice_status() -> dict:
    engine = voice_engine_path()
    model = voice_model_path()
    return {
        "ready": voice_ready(),
        "engine": str(engine) if engine else "",
        "model": str(model) if model else "",
        "binding": voice_binding_ok(),
        "error": _voice_state.get("error", ""),
    }


def _voice_prepare() -> None:
    if _voice_state.get("loaded"):
        return
    if str(VOICE_PY) not in sys.path:
        sys.path.insert(0, str(VOICE_PY))
    engine = voice_engine_path()
    if engine is None:
        raise RuntimeError("движок распознавания не установлен")
    os.environ["TRANSCRIBE_LIBRARY"] = str(engine)
    _voice_state["loaded"] = True
    _voice_state["error"] = ""


def voice_transcribe(pcm: bytes) -> dict:
    """pcm — сырые int16, 16 кГц, моно. Возвращает распознанный текст."""
    if not voice_ready():
        raise RuntimeError("голосовая модель не установлена — скачайте её в настройках")
    if len(pcm) < 3200:                       # меньше 0,1 с
        raise ValueError("запись слишком короткая")
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    pcm_f = array.array("f", (s / 32768.0 for s in samples))
    started = time.time()
    with _voice_lock:
        try:
            _voice_prepare()
            import transcribe_cpp  # noqa: PLC0415 — грузится по требованию
            with transcribe_cpp.Model(str(voice_model_path())) as model:
                with model.session() as session:
                    result = session.run(pcm_f)
                    text = (getattr(result, "text", "") or "").strip()
        except Exception as exc:  # noqa: BLE001
            _voice_state["error"] = f"{type(exc).__name__}: {exc}"
            raise
    return {"text": text, "seconds": round(len(pcm_f) / 16000, 2),
            "elapsed": round(time.time() - started, 2)}


ASSETS_DIR = DATA / "assets"
SHEET_UI = UI_DIR / "sheet.html"
_sheet_core = None


def sheet_core():
    """Модуль встроенного редактора спрайт-листа (порт Node-сервера)."""
    global _sheet_core
    if _sheet_core is None:
        path = str(ROOT / "sheet_py")
        if path not in sys.path:
            sys.path.insert(0, path)
        import core as core_mod  # noqa: PLC0415 — грузится по требованию
        core_mod.init()
        _sheet_core = core_mod
    return _sheet_core


def sheet_dialog(kind: str, start: str = "") -> str:
    """Системный диалог выбора папки/файла (тот же dialog.ps1, что в редакторе)."""
    script = ASSETS_DIR / "dialog.ps1"
    title = {"game": "Папка игры Godot (где лежит project.godot)",
             "frames": "Папка с кадрами", "godot": "Godot.exe",
             "comfy": "ComfyUI: Comfy Desktop.exe, ComfyUI.exe или run_nvidia_gpu.bat"}.get(kind, "")
    args = ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-Kind", "exe" if kind in ("godot", "comfy") else "folder", "-Title", title]
    if start:
        p = Path(start)
        if p.exists():
            args += ["-Start", str(p.parent if p.is_file() else p)]
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900, creationflags=flags)
    except subprocess.TimeoutExpired:
        return ""
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _install_llama() -> str:
    _set_progress(kind="llama", group="agent", file="llama.cpp", message="ищу сборку llama.cpp",
                  done=0, total=0)
    req = urllib.request.Request(
        "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest",
        headers={"User-Agent": "SpriteAnimStudio/0.1", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        rel = json.loads(r.read().decode("utf-8"))
    assets = rel.get("assets") or []
    pick = None
    for pref in ("win-cuda-x64", "win-cpu-x64"):
        pick = next((a for a in assets if pref in a["name"] and a["name"].endswith(".zip")), None)
        if pick:
            break
    if not pick:
        raise RuntimeError("в последнем релизе llama.cpp нет сборки для Windows")
    dest = agent_home() / "llama" / pick["name"]
    _download(pick["browser_download_url"], dest, group="agent", name="llama.cpp")
    _set_progress(phase="extract", message="распаковываю llama.cpp", done=0, total=0)
    target = agent_llama_dir()
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["tar", "-xf", str(dest), "-C", str(target)], check=True,
                   creationflags=0x08000000 if os.name == "nt" else 0)
    # llama.cpp кладёт файлы в подпапку — поднимаем её содержимое наверх
    subs = [p for p in target.iterdir() if p.is_dir()]
    if subs and not (target / "llama-server.exe").is_file():
        inner = subs[0]
        for p in list(inner.iterdir()):
            shutil.move(str(p), str(target / p.name))
        try:
            inner.rmdir()
        except OSError:
            pass
    dest.unlink(missing_ok=True)
    return f"llama.cpp: {pick['name']}"


def install_models(group_id: str) -> None:
    group = next((g for g in MODEL_GROUPS if g["id"] == group_id), None)
    if group is None:
        raise RuntimeError("неизвестная группа моделей")
    missing = [f for f in group["files"] if not _file_status(f)["present"]]
    if group_id == "agent" and not agent_server_path():
        missing_llama = True
    else:
        missing_llama = False
    if not missing and not missing_llama:
        _set_progress(active=False, message="всё уже на месте")
        return
    for item in missing:
        _download_file(item, group)
    if missing_llama:
        _install_llama()


def _install_worker(group_id: str) -> None:
    try:
        install_models(group_id)
        _set_progress(active=False, phase="done", kind="", group=group_id,
                      message="готово", done=0, total=0, speed=0.0)
    except Exception as exc:  # noqa: BLE001
        _set_progress(active=False, phase="error", error=str(exc), message=str(exc))
    finally:
        _cancel_flag.clear()


def download_group(group_id: str) -> dict:
    if setup_progress().get("active"):
        return {"ok": False, "error": "уже идёт загрузка"}
    state = setup_progress()
    _cancel_flag.clear()
    _set_progress(active=True, kind="model", group=group_id, phase="download",
                  error="", message="начинаю", file="", done=0, total=0, speed=0.0)
    threading.Thread(target=_install_worker, args=(group_id,), daemon=True).start()
    return {"ok": True, "state": state}


def cancel_download() -> dict:
    _cancel_flag.set()
    _set_progress(message="останавливаю…")
    return {"ok": True}


# ------------------------------------------------------- установка ComfyUI
_comfy_state: dict = {"phase": "", "message": "", "error": "", "done": 0, "total": 0}


def comfy_install_status() -> dict:
    with _progress_lock:
        p = dict(_progress)
    return {"active": bool(p.get("active") and p.get("kind") == "comfy"), **p}


def _comfy_release_asset() -> dict:
    import re as _re
    req = urllib.request.Request(
        "https://api.github.com/repos/comfyanonymous/ComfyUI/releases/latest",
        headers={"User-Agent": "SpriteAnimStudio/0.1", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        rel = json.loads(r.read().decode("utf-8"))
    rx = _re.compile(COMFY_PORTABLE_RE, _re.I)
    for a in rel.get("assets") or []:
        if rx.search(a["name"]):
            return a
    raise RuntimeError("в релизе ComfyUI не нашёлся windows-portable архив")


def _comfy_install_worker() -> None:
    try:
        _set_progress(active=True, kind="comfy", group="comfy", phase="download",
                      message="ищу сборку ComfyUI", file="", done=0, total=0,
                      speed=0.0, error="")
        asset = _comfy_release_asset()
        dest = ROOT / "ComfyUI" / asset["name"]
        _download(asset["browser_download_url"], dest, group="comfy", name=asset["name"])
        _set_progress(phase="extract", message="распаковываю ComfyUI", done=0, total=0)
        target = ROOT / "ComfyUI"
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xf", str(dest), "-C", str(target)], check=True,
                       creationflags=0x08000000 if os.name == "nt" else 0)
        dest.unlink(missing_ok=True)
        _set_progress(active=False, kind="comfy", phase="done",
                      message="ComfyUI распакован", done=0, total=0, speed=0.0)
    except Exception as exc:  # noqa: BLE001
        _set_progress(active=False, kind="comfy", phase="error", error=str(exc),
                      message=str(exc))


def comfy_install() -> dict:
    if setup_progress().get("active"):
        return {"ok": False, "error": "уже идёт загрузка"}
    _cancel_flag.clear()
    _set_progress(active=True, kind="comfy", group="comfy", phase="download",
                  message="начинаю", file="", done=0, total=0, speed=0.0, error="")
    threading.Thread(target=_comfy_install_worker, daemon=True).start()
    return {"ok": True}


def comfy_portable_dir() -> Path:
    return ROOT / "ComfyUI" / "ComfyUI_windows_portable"


def comfy_run_portable() -> dict:
    """Запускает установленную рядом сборку ComfyUI (run_nvidia_gpu.bat)."""
    base = comfy_portable_dir()
    bat = next((p for p in base.glob("run_*.bat") if p.is_file()), None) if base.is_dir() else None
    if bat is None:
        raise RuntimeError("сборка ComfyUI рядом с программой не найдена")
    flags = 0x00000008 if os.name == "nt" else 0        # DETACHED_PROCESS
    subprocess.Popen(["cmd", "/c", "start", "", bat.name], cwd=str(base),
                     creationflags=flags, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    return {"ok": True, "started": bat.name}


def job_status(prompt_id: str) -> dict:
    """Свести /history и /queue в одно понятное состояние."""
    tracked = jobs_load().get(str(prompt_id)) or {}
    if tracked.get("kind") == "upscale":
        return {
            "state": tracked.get("state") or "queued",
            "error": tracked.get("error") or "",
            "outputs": tracked.get("outputs") or [],
            "local": tracked.get("local") or {},
            "done": tracked.get("done") or 0,
            "total": tracked.get("total") or 0,
            "meta": {k: tracked[k] for k in ("name", "factor", "run", "src") if tracked.get(k)},
        }
    try:
        hist = comfy_json(f"/history/{prompt_id}", timeout=15)
    except Exception as exc:  # noqa: BLE001
        return {"state": "unknown", "error": str(exc), "outputs": []}
    entry = hist.get(prompt_id) if isinstance(hist, dict) else None
    if entry:
        status = entry.get("status") or {}
        ok = status.get("status_str", "success") == "success" and not status.get("error")
        outputs = []
        texts = []
        for node_id, out in (entry.get("outputs") or {}).items():
            for t in out.get("text") or []:
                if isinstance(t, str):
                    texts.append(t)
            for key in ("videos", "gifs", "images", "video"):
                for item in out.get(key) or []:
                    if not isinstance(item, dict) or "filename" not in item:
                        continue
                    kind = "video" if str(item["filename"]).lower().endswith((".mp4", ".webm", ".mkv", ".gif")) else "image"
                    outputs.append({
                        "node": node_id, "key": key, "kind": kind,
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    })
        err = ""
        for m in status.get("messages") or []:
            if isinstance(m, list) and m and m[0] in ("execution_error", "execution_interrupted"):
                err = str((m[1] or {}).get("exception_message") or m[0])
        result = {"state": "done" if ok else "error", "error": err, "outputs": outputs,
                  "texts": texts,
                  "completed": bool(status.get("completed")), "meta": _history_meta(entry)}
        if ok:
            result["local"] = collect_outputs(result)
        return result
    try:
        q = comfy_json("/queue", timeout=10)
    except Exception:
        q = {}
    running = [x[1] for x in (q.get("queue_running") or []) if len(x) > 1]
    pending = [x[1] for x in (q.get("queue_pending") or []) if len(x) > 1]
    if prompt_id in running:
        return {"state": "running", "outputs": []}
    if prompt_id in pending:
        return {"state": "queued", "outputs": []}
    return {"state": "unknown", "outputs": []}


# ------------------------------------------------------------ убрать фон
# Qwen Image 2.1 (ComfyUI, официальный шаблон background removal): модель
# отдаёт PNG с настоящей альфой, поэтому хромакей здесь не нужен.
BG_PROMPT = "Remove the background, and output a PNG image"
BG_UNET = ["qwen_image_2.1_int8_convrot.safetensors"]
BG_CLIP = ["qwen3vl_8b_int8_convrot.safetensors",
           "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors",
           "qwen_2.5_vl_7b_fp8_scaled.safetensors"]
BG_VAE = ["qwen_image_2.1_vae_bf16.safetensors", "qwen_image_vae.safetensors"]


def _choices(info: dict, node: str, field: str) -> list[str]:
    spec = (((info.get(node) or {}).get("input") or {}).get("required") or {}).get(field)
    if not spec:
        return []
    first = spec[0]
    if isinstance(first, list):          # старый формат: ["a.safetensors", ...]
        return [str(x) for x in first]
    if isinstance(first, str) and first.upper() == "COMBO" and len(spec) > 1:
        # новый формат io.Combo: ["COMBO", {"options": [...]}]
        meta = spec[1] if isinstance(spec[1], dict) else {}
        return [str(x) for x in (meta.get("options") or [])]
    return []


def _pick(options: list[str], wanted: list[str], hint: str) -> str:
    for name in wanted:
        if name in options:
            return name
    for name in options:
        if hint in name.lower():
            return name
    return ""


def bg_models(info: dict) -> dict:
    """Что из установленного подходит для вырезания фона."""
    unets = _choices(info, "UNETLoader", "unet_name")
    clips = _choices(info, "CLIPLoader", "clip_name")
    vaes = _choices(info, "VAELoader", "vae_name")

    return {
        "unet": _pick(unets, BG_UNET, "qwen_image_2.1") or _pick(unets, [], "qwen_image"),
        "clip": _pick(clips, BG_CLIP, "qwen3vl") or _pick(clips, [], "qwen"),
        "vae": _pick(vaes, BG_VAE, "qwen_image"),
        "nodes": all(n in info for n in ("TextEncodeQwenImage21", "QwenImage21Cache",
                                         "ComfySwitchNode", "SaveImageAdvanced")),
    }


def build_bg_graph(uploaded: str, prompt: str, resolution: int, seed: int, run: str,
                   models: dict) -> dict:
    # 0 — «как в исходной картинке»: узел сам считает размер по референсу.
    res = int(resolution) if resolution in (0, 768, 1024, 1536) else 1024
    latent = res or 1024
    return {
        "451": {"class_type": "UNETLoader",
                "inputs": {"unet_name": models["unet"], "weight_dtype": "default"}},
        "453": {"class_type": "CLIPLoader",
                "inputs": {"clip_name": models["clip"], "type": "qwen_image", "device": "default"}},
        "454": {"class_type": "VAELoader", "inputs": {"vae_name": models["vae"]}},
        "470": {"class_type": "LoadImage", "inputs": {"image": uploaded}},
        "469": {"class_type": "QwenImage21Cache",
                "inputs": {"model": ["451", 0], "device": "auto", "dtype": "default"}},
        "474": {"class_type": "TextEncodeQwenImage21",
                "inputs": {"clip": ["453", 0], "images.image_1": ["470", 0], "vae": ["454", 0],
                           "prompt": prompt, "negative_prompt": "", "resolution": res}},
        "456": {"class_type": "EmptyLatentImage",
                "inputs": {"width": latent, "height": latent, "batch_size": 1}},
        "468": {"class_type": "ComfySwitchNode",
                "inputs": {"switch": False, "on_false": ["474", 2], "on_true": ["456", 0]}},
        "458": {"class_type": "KSampler",
                "inputs": {"model": ["469", 0], "positive": ["474", 0], "negative": ["474", 1],
                           "latent_image": ["468", 0], "seed": seed, "steps": 25, "cfg": 1,
                           "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "457": {"class_type": "VAEDecode", "inputs": {"samples": ["458", 0], "vae": ["454", 0]}},
        "461": {"class_type": "SaveImageAdvanced",
                "inputs": {"images": ["457", 0], "filename_prefix": f"SpriteAnim/bg/{run}/cut",
                           "format": "png", "format.bit_depth": "8-bit",
                           "format.input_color_space": "sRGB"}},
    }


# ------------------------------------------------------ генерация картинок
# Qwen Image 2.1 t2i по официальному шаблону ComfyUI. Улучшатель промпта
# (второй CLIPLoader + TextGenerate) не используется: его энкодера нет в проекте,
# а наш агент по скиллам делает то же самое осмысленнее.
IMAGE_MODELS = [
    {
        "id": "qwen21",
        "title": "Qwen Image 2.1",
        "hint": "качество, 25 шагов",
        "builder": "qwen21",
        "unet": ["qwen_image_2.1_int8_convrot.safetensors"],
        "clip": ["qwen3vl_8b_int8_convrot.safetensors"],
        "vae": ["qwen_image_2.1_vae_bf16.safetensors"],
        "nodes": ["TextEncodeQwenImage21", "QwenImage21Cache", "SaveImageAdvanced"],
        "steps": 25,
        "step_options": [16, 25, 40],
        "cfg": 1.0,
        "enhancer": {"clip": ["qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors"]},
    },
]

ASPECTS = {"1:1": (1, 1), "16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3), "3:4": (3, 4)}

# Системный промпт улучшайзера — из официального шаблона ComfyUI (10 КБ).
ENHANCER_FILE = ROOT / "prompts" / "qwen_enhancer.md"
ENHANCER_SYSTEM = ENHANCER_FILE.read_text("utf-8") if ENHANCER_FILE.is_file() else ""


def image_size(base: int, aspect: str) -> tuple[int, int]:
    """Длинная сторона = base, короткая — по пропорции, кратно 16."""
    a, b = ASPECTS.get(aspect, (1, 1))
    base = max(256, min(2048, int(base) or 1024))
    if a >= b:
        w, h = base, round(base * b / a / 16) * 16
    else:
        w, h = round(base * a / b / 16) * 16, base
    return max(256, w), max(256, h)


def image_models(info: dict) -> list[dict]:
    unets = _choices(info, "UNETLoader", "unet_name")
    clips = _choices(info, "CLIPLoader", "clip_name")
    vaes = _choices(info, "VAELoader", "vae_name")
    out = []
    for spec in IMAGE_MODELS:
        unet = _pick(unets, spec["unet"], "qwen_image_2.1")
        clip = _pick(clips, spec["clip"], "qwen3vl")
        vae = _pick(vaes, spec["vae"], "qwen_image")
        nodes = all(n in info for n in spec["nodes"])
        missing = []
        if not nodes:
            missing.append("ноды ComfyUI")
        if not unet:
            missing.append("diffusion-модель")
        if not clip:
            missing.append("text encoder")
        if not vae:
            missing.append("VAE")
        enhancer = ""
        if spec.get("enhancer"):
            enhancer = _pick(clips, spec["enhancer"]["clip"], "pe_t2i")
            if enhancer and not (ENHANCER_SYSTEM and "TextGenerate" in info and "PrimitiveStringMultiline" in info):
                enhancer = ""
        out.append({"id": spec["id"], "title": spec["title"], "hint": spec["hint"],
                    "builder": spec.get("builder", ""),
                    # править присланные картинки умеют qwen21 и minimax (images.image_N)
                    "ref": spec.get("builder") in ("qwen21", "minimax"),
                    "skill": SKILL_FOR.get(spec["id"], ""),
                    "steps": spec["steps"], "step_options": spec.get("step_options", []),
                    "cfg": spec["cfg"], "enhancer": enhancer,
                    "ready": not missing, "missing": missing,
                    "files": {"unet": unet, "clip": clip, "vae": vae}})
    return out


def build_image_graph(model: dict, prompt: str, negative: str, width: int, height: int,
                      seed: int, steps: int, cfg: float, run: str,
                      enhance: bool = False, enhancer_clip: str = "",
                      ref_name: str = "", refs: list[str] | None = None) -> dict:
    """refs — имена загруженных картинок: image_1 — основная (её правим), дальше референсы.

    Qwen 2.1 и MiniMax H3 Image принимают `images.image_1..N` (autogrow); у MiniMax
    image_1 — картинка для правки, а в промпте на неё ссылаются как <Picture 1>.
    """
    names = [n for n in (refs if refs is not None else ([ref_name] if ref_name else [])) if n]
    files = model["files"]
    prefix = f"SpriteAnim/img/{run}/img"
    save = {"class_type": "SaveImageAdvanced",
            "inputs": {"images": ["457", 0], "filename_prefix": prefix,
                       "format": "png", "format.bit_depth": "8-bit",
                       "format.input_color_space": "sRGB"}}
    extra = {}
    prompt_input = prompt
    if enhance and enhancer_clip:
        extra = {
            "473": {"class_type": "CLIPLoader",
                    "inputs": {"clip_name": enhancer_clip, "type": "stable_diffusion",
                               "device": "default"}},
            "475": {"class_type": "PrimitiveStringMultiline",
                    "inputs": {"value": ENHANCER_SYSTEM}},
            "471": {"class_type": "TextGenerate",
                    "inputs": {"clip": ["473", 0], "prompt": prompt, "max_length": 4096,
                               "sampling_mode": "on",
                               "sampling_mode.temperature": 1,
                               "sampling_mode.top_k": 20,
                               "sampling_mode.top_p": 0.95,
                               "sampling_mode.min_p": 0,
                               "sampling_mode.repetition_penalty": 1,
                               "sampling_mode.seed": 0,
                               "sampling_mode.presence_penalty": 1.5,
                               "thinking": True, "use_default_template": True,
                               "mtp": "auto", "system_prompt": ["475", 0]}},
            "472": {"class_type": "PreviewAny", "inputs": {"source": ["471", 0]}},
        }
        prompt_input = ["471", 0]
    if model.get("builder") == "minimax":
        cond = {"clip": ["453", 0], "prompt": prompt_input,
                "width": width, "height": height}
        extra_ref = {}
        if names:
            for i, name in enumerate(names[:8], 1):
                nid = str(490 + i)
                extra_ref[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
                cond[f"images.image_{i}"] = [nid, 0]
            cond["vae"] = ["454", 0]
        return {
            "451": {"class_type": "UNETLoader",
                    "inputs": {"unet_name": files["unet"], "weight_dtype": "default"}},
            "453": {"class_type": "CLIPLoader",
                    "inputs": {"clip_name": files["clip"], "type": "minimax", "device": "default"}},
            "454": {"class_type": "VAELoader", "inputs": {"vae_name": files["vae"]}},
            "455": {"class_type": "MiniMaxH3ImageConditioning", "inputs": cond},
            "456": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["455", 0]}},
            "458": {"class_type": "KSampler",
                    "inputs": {"model": ["451", 0], "positive": ["455", 0],
                               "negative": ["456", 0], "latent_image": ["455", 1],
                               "seed": seed, "steps": steps, "cfg": cfg,
                               "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
            "457": {"class_type": "VAEDecode", "inputs": {"samples": ["458", 0], "vae": ["454", 0]}},
            "461": save,
            **extra,
            **extra_ref,
        }
    if model.get("builder") == "klein":
        return {
            "451": {"class_type": "UNETLoader",
                    "inputs": {"unet_name": files["unet"], "weight_dtype": "default"}},
            "453": {"class_type": "CLIPLoader",
                    "inputs": {"clip_name": files["clip"], "type": "flux2", "device": "default"}},
            "454": {"class_type": "VAELoader", "inputs": {"vae_name": files["vae"]}},
            "455": {"class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["453", 0], "text": prompt}},
            "456": {"class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["453", 0], "text": negative or ""}},
            "457": {"class_type": "EmptyFlux2LatentImage",
                    "inputs": {"width": width, "height": height, "batch_size": 1}},
            "458": {"class_type": "Flux2Scheduler",
                    "inputs": {"steps": steps, "width": width, "height": height}},
            "459": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
            "460": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
            "461": {"class_type": "CFGGuider",
                    "inputs": {"model": ["451", 0], "positive": ["455", 0],
                               "negative": ["456", 0], "cfg": cfg}},
            "462": {"class_type": "SamplerCustomAdvanced",
                    "inputs": {"noise": ["460", 0], "guider": ["461", 0], "sampler": ["459", 0],
                               "sigmas": ["458", 0], "latent_image": ["457", 0]}},
            "463": {"class_type": "VAEDecode", "inputs": {"samples": ["462", 0], "vae": ["454", 0]}},
            "464": dict(save, inputs=dict(save["inputs"], images=["463", 0])),
        }
    extra_ref = {}
    ref_inputs: dict = {}
    if names:
        for i, name in enumerate(names[:8], 1):
            nid = str(490 + i)
            extra_ref[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
            ref_inputs[f"images.image_{i}"] = [nid, 0]
        extra_ref["477"] = {"class_type": "ComfySwitchNode",
                            "inputs": {"switch": False, "on_false": ["452", 2],
                                       "on_true": ["456", 0]}}
    return {
        "451": {"class_type": "UNETLoader",
                "inputs": {"unet_name": files["unet"], "weight_dtype": "default"}},
        "453": {"class_type": "CLIPLoader",
                "inputs": {"clip_name": files["clip"], "type": "qwen_image", "device": "default"}},
        "454": {"class_type": "VAELoader", "inputs": {"vae_name": files["vae"]}},
        "452": {"class_type": "TextEncodeQwenImage21",
                "inputs": {"clip": ["453", 0], "prompt": prompt_input,
                           "negative_prompt": negative,
                           "resolution": max(width, height) if names else 1024,
                           **ref_inputs,
                           **({"vae": ["454", 0]} if names else {})}},
        "456": {"class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1}},
        "480": {"class_type": "QwenImage21Cache",
                "inputs": {"model": ["451", 0], "device": "auto", "dtype": "default"}},
        "458": {"class_type": "KSampler",
                "inputs": {"model": ["480", 0], "positive": ["452", 0], "negative": ["452", 1],
                           "latent_image": ["477", 0] if names else ["456", 0],
                           "seed": seed, "steps": steps, "cfg": cfg,
                           "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "457": {"class_type": "VAEDecode", "inputs": {"samples": ["458", 0], "vae": ["454", 0]}},
        "461": save,
        **extra,
        **extra_ref,
    }


# --------------------------------------------------- агент по промптам
# Локальный llama.cpp + Gemma 4 12B (мультимодальная) — тот же набор файлов,
# что использует референсное приложение, но свой порт и свой запуск.
# Пути берутся из agent_home(): текущая папка на SSD или <программа>/models/agent.
AGENT_PORT = 8281
AGENT_CTX = 16384
AGENT_THREADS = 14
SKILL_DIR = ROOT / "skills"

# Какая модель изображений каким скиллом пишется.
SKILL_FOR = {
    "qwen21": "qwen-image-2-1-director-prompt",
    "klein": "flux2-klein",
    "minimax": "minimax-h3-image",
    "sprite": "sprite-animation",
    "bg": "qwen-image-2-1-director-prompt",
}

_agent_state: dict = {"proc": None, "port": 0, "starting": False}
_agent_lock = threading.Lock()

AGENT_RULES = (
    "\n\n---\n"
    "Ты работаешь внутри приложения SpriteAnim Studio. Ответь в том формате, который "
    "требует скилл выше:\n"
    "1) первой строкой — «Формат кадра: <1:1, 16:9, 9:16, 4:3 или 3:4>»;\n"
    "2) короткая фраза по-русски, что это за стиль (одна строка);\n"
    "3) сам промпт на английском в блоке ```prompt … ```.\n"
    "Если скилл требует другого — следуй скиллу. Никаких пояснений, списков и переводов "
    "промпта.\n"
)

def _agent_alive(port: int, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def free_ram_gb() -> float:
    """Сколько физической памяти свободно, ГБ (Windows; иначе — «много»)."""
    if os.name != "nt":
        return 99.0
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return st.ullAvailPhys / 1024 ** 3
    except Exception:  # noqa: BLE001
        return 99.0


def comfy_queue_empty() -> bool:
    """Не трогаем ComfyUI, если он что-то считает."""
    try:
        q = comfy_json("/queue", timeout=5)
        return not q.get("queue_running") and not q.get("queue_pending")
    except Exception:  # noqa: BLE001
        return False


def comfy_unload_models() -> bool:
    """Просим ComfyUI выгрузить модели и освободить память (RAM/VRAM)."""
    try:
        data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        req = urllib.request.Request(COMFY + "/free", data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return 200 <= r.status < 300
    except Exception:  # noqa: BLE001
        return False


def _agent_priority(proc, background: bool) -> None:
    """Windows: во время загрузки модели уводим процесс в background mode.

    Модель лежит на USB-диске: чтение 6,7 ГБ с обычным приоритетом ввода-вывода
    на секунды подвешивает ввод (курсор ходит, клики не доходят). Background mode
    даёт самый низкий приоритет CPU и I/O, поэтому система остаётся отзывчивой,
    а после загрузки приоритет возвращается к below-normal (быстро, но не в ущерб UI).
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x0200, False, proc.pid)  # PROCESS_SET_INFORMATION
        if not handle:
            return
        try:
            # 0x00100000 — PROCESS_MODE_BACKGROUND_BEGIN, 0x00200000 — ..._END
            k32.SetPriorityClass(handle, 0x00100000 if background else 0x00200000)
        finally:
            k32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 — приоритет не критичен, запуск важнее
        pass


def _agent_boot(proc) -> None:
    """Ждёт готовности сервера агента и снимает background-режим."""
    ok = False
    for _ in range(1200):         # до 10 минут: модель читается с USB-диска
        time.sleep(0.5)
        if _agent_alive(AGENT_PORT):
            ok = True
            break
        if proc.poll() is not None:
            break
    _agent_priority(proc, background=False)
    with _agent_lock:
        _agent_state["starting"] = False
        if not ok:
            _agent_state.update(proc=None, port=0)


def agent_info(port: int = 0, owned: bool = False) -> dict:
    model = agent_model_path()
    return {
        "running": bool(port),
        "starting": bool(_agent_state.get("starting")),
        "port": port,
        "owned": owned,
        "model": model.name if model.is_file() else "",
        "vision": agent_mmproj_path().is_file(),
        "skills": sorted(p.name for p in SKILL_DIR.iterdir() if (p / "SKILL.md").is_file())
        if SKILL_DIR.is_dir() else [],
    }


def agent_log_tail(chars: int = 300) -> str:
    """Последние строки лога llama-server: почему агент не поднялся."""
    try:
        data = AGENT_LOG.read_bytes()[-chars * 4:]
    except OSError:
        return ""
    text = data.decode("utf-8", "replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " | ".join(lines[-4:])[:chars]


def agent_need_gb() -> float:
    """Сколько RAM нужно агенту: веса на диске + буферы и KV-кэш."""
    model = agent_model_path()
    try:
        weights = model.stat().st_size / 1024 ** 3
    except OSError:
        weights = 7.0
    return weights * 1.15 + 1.0


def agent_start(wait: bool = True) -> dict:
    """Запускает агента. wait=False отвечает сразу («starting»), загрузка — в фоне."""
    freed = False
    with _agent_lock:
        proc = _agent_state.get("proc")
        port = _agent_state.get("port") or 0
        if proc is not None and proc.poll() is None and port and _agent_alive(port):
            return agent_info(port, True)
        if _agent_alive(AGENT_PORT):
            _agent_state.update(port=AGENT_PORT)
            return agent_info(AGENT_PORT, False)

        booting = proc if (proc is not None and proc.poll() is None) else None
        if booting is None:
            exe = agent_server_path()
            model = agent_model_path()
            mmproj = agent_mmproj_path()
            if exe is None or not model.is_file():
                return {"running": False, "starting": False,
                        "error": "нет llama-server.exe или модели Gemma в "
                                 f"{agent_home()}", "port": 0, "owned": False,
                        "model": "", "vision": False, "skills": []}
            cmd = [str(exe), "-m", str(model), "--mmproj", str(mmproj),
                   "-c", str(AGENT_CTX), "-t", str(AGENT_THREADS),
                   # низкий приоритет и без прогрева: не отбираем машину у интерфейса
                   "--prio", "-1", "--no-warmup",
                   "--host", "127.0.0.1", "--port", str(AGENT_PORT)]
            flags = 0x08000000 if os.name == "nt" else 0        # CREATE_NO_WINDOW
            if os.name == "nt":
                flags |= 0x00004000                              # BELOW_NORMAL_PRIORITY_CLASS
            # Один тяжёлый движок за раз: ComfyUI после генерации держит модели
            # в RAM и VRAM, а llama-server с ними не поднимается (падает при
            # старте). Перед агентом выгружаем ComfyUI, если он простаивает;
            # следующая генерация перезагрузит модели с диска.
            if comfy_queue_empty():
                freed = comfy_unload_models()
                print(f"[agent] выгрузка ComfyUI перед агентом: "
                      f"{'да' if freed else 'нечего выгружать'}; "
                      f"свободно {free_ram_gb():.1f} ГБ RAM, "
                      f"нужно ~{agent_need_gb():.1f} ГБ")
            else:
                print("[agent] ComfyUI занят генерацией — запускаю агента как есть")
            try:
                try:
                    CACHE_DIR.mkdir(exist_ok=True)
                    log = open(AGENT_LOG, "wb")       # свежий лог на каждый запуск
                except OSError:
                    log = subprocess.DEVNULL
                booting = subprocess.Popen(cmd, cwd=str(exe.parent), stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=flags)
                if log is not subprocess.DEVNULL:
                    log.close()          # у ребёнка своя копия handle
            except Exception as exc:  # noqa: BLE001
                return {"running": False, "starting": False,
                        "error": f"не удалось запустить агента: {exc}",
                        "port": 0, "owned": False, "model": "", "vision": False, "skills": []}
            _agent_state.update(proc=booting, port=AGENT_PORT, starting=True)
            # background mode ставим в фоне: llama.cpp сам выставляет приоритет при старте
            threading.Timer(2.0, _agent_priority, args=(booting, True)).start()
            threading.Thread(target=_agent_boot, args=(booting,), daemon=True).start()
        else:
            _agent_state["starting"] = True

    if not wait:
        return {**agent_info(0, True), "starting": True, "freed": freed}

    for _ in range(1200):         # до 10 минут: 12B с USB-диска грузится долго
        time.sleep(0.5)
        if _agent_alive(AGENT_PORT):
            return {**agent_info(AGENT_PORT, True), "freed": freed}
        if booting.poll() is not None:
            _agent_state.update(proc=None, port=0, starting=False)
            tail = agent_log_tail()
            print(f"[agent] закрылся при старте: {tail or 'без вывода'}")
            return {"running": False, "starting": False,
                    "error": "агент запустился и сразу закрылся"
                             + (f": {tail}" if tail else ""),
                    "port": 0, "owned": False, "model": "", "vision": False, "skills": []}
    _agent_state.update(starting=False)
    return {"running": False, "starting": False, "error": "агент не ответил за 10 минут",
            "port": 0, "owned": False, "model": "", "vision": False, "skills": []}


def agent_stop() -> dict:
    with _agent_lock:
        proc = _agent_state.get("proc")
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=6)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        _agent_state.update(proc=None, port=0, starting=False)
        return agent_info(0, False)


def _agent_quit():
    proc = _agent_state.get("proc")
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def shutdown_app() -> None:
    """Гасит агента и выходит: приложение работает без консоли."""
    for fn in (_agent_quit,):
        try:
            fn()
        except Exception:  # noqa: BLE001
            pass
    os._exit(0)


def skill_text(skill_id: str) -> str:
    path = SKILL_DIR / skill_id / "SKILL.md"
    if not path.is_file():
        return ""
    raw = path.read_text("utf-8")
    # frontmatter (name/description) модели не нужен
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end > 0:
            raw = raw[end + 4:]
    return raw.strip()


def parse_agent_reply(text: str) -> tuple[str, str]:
    body = (text or "").strip()
    aspect = ""
    m = (re.search(r"(?:ASPECT|Формат кадра)\s*:?\s*([0-9]{1,2}:[0-9]{1,2})", body, re.I)
         or re.search(r"\b(1:1|16:9|9:16|4:3|3:4)\b", body))
    if m:
        aspect = m.group(1)
    fence = re.search(r"```(?:prompt)?\s*\n(.*?)```", body, re.S)
    if fence:
        return fence.group(1).strip(), aspect
    m = re.search(r"PROMPT:\s*", body, re.I)
    if m:
        body = body[m.end():].lstrip()
    # без блока: убираем служебную первую строку с форматом кадра
    body = re.sub(r"^(?:ASPECT|Формат кадра)\s*:?[^\n]*\n+", "", body, flags=re.I)
    return body.strip(), aspect


AGENT_VISION = (
    "Опиши изображение как художник-референс: кто или что в кадре, поза и ракурс, "
    "одежда и материалы, точные цвета, стиль (фото/вектор/3D/аниме), фон, свет, "
    "композиция и настроение. Только наблюдаемое, без оценок и без советов. "
    "Пиши по-русски, плотно, 5–12 предложений."
)


def _agent_chat_stream(port: int, messages: list, on_delta, max_tokens: int = 900,
                       think: bool = False) -> str:
    """Ответ агента кусками: каждый delta отдаётся в on_delta, в конце — полный текст."""
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": bool(think)},
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    text = ""
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk in ("[DONE]", ""):
                if chunk == "[DONE]":
                    break
                continue
            try:
                event = json.loads(chunk)
            except Exception:
                continue
            delta = ((event.get("choices") or [{}])[0].get("delta") or {}).get("content") or ""
            if delta:
                text += delta
                on_delta(delta)
    return text


def _agent_chat(port: int, messages: list, max_tokens: int = 900,
                think: bool = False) -> str:
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "stream": False,
        # «Быстро» — без рассуждений (по умолчанию, как в референсном приложении);
        # «Глубоко» — с thinking, для сложных сцен.
        "chat_template_kwargs": {"enable_thinking": bool(think)},
    }
    res = _http_json(f"http://127.0.0.1:{port}/v1/chat/completions", payload, timeout=600)
    return ((res.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


TRANSLATE_SYSTEM = (
    "You are a precise translator for game-art and video prompts. "
    "Translate the user's text into Russian. Keep the meaning exact, keep "
    "technical terms, numbers, field names, labels and the original structure. "
    "Do not add, remove, explain or comment on anything. "
    "Output only the translation, without quotation marks."
)


def translate_messages(text: str) -> list[dict]:
    return [{"role": "system", "content": TRANSLATE_SYSTEM},
            {"role": "user", "content": text}]


def translate_max_tokens(text: str) -> int:
    """Русский текст чуть длиннее английского: токенов с запасом, но без лишних."""
    return max(400, min(1600, int(len(text) / 1.7) + 150))


def _translate_clean(out: str) -> str:
    out = (out or "").strip()
    for a, b in (('"', '"'), ("«", "»"), ("“", "”")):
        if out.startswith(a) and out.endswith(b):
            out = out[1:-1].strip()
    return out


def translate_text(text: str) -> str:
    """Перевод промпта на русский локальным агентом (без интернета)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("пустой текст")
    if len(text) > 4000:
        text = text[:4000]
    info = agent_start()
    if not info.get("running"):
        raise RuntimeError(info.get("error") or "агент не запущен")
    port = info["port"]
    out = _translate_clean(_agent_chat(port, translate_messages(text),
                                       max_tokens=translate_max_tokens(text), think=False))
    if not out:
        raise RuntimeError("агент не вернул перевод")
    return out


def _looks_like_prompt(text: str) -> bool:
    """Грубая проверка: это английский промпт, а не рассуждение и не русский текст."""
    if len(text) < 40:
        return False
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    cyr = sum(1 for ch in text if "а" <= ch.lower() <= "я")
    return latin >= 20 and latin > cyr * 3


# Строка про намерение: не меняет скилл и правила формата, только подсказывает,
# правим ли мы присланную картинку или рисуем новое по образцу.
AGENT_INTENT = {
    "edit": ("\n\n---\nРежим: ПРАВКА присланной картинки. Формула промпта: что изменить + "
             "что обязательно сохранить (лицо, поза, одежда, фон, свет).\n"),
    "new": ("\n\n---\nРежим: НОВОЕ изображение по образцу. Опиши нового персонажа словами, "
            "опираясь на стиль и палитру образца. Не пиши «change», «keep the face», "
            "«the same image»: это не правка.\n"),
}


MULTI_HINT = {
    "minimax": ("\n\nКартинок несколько: ссылайся на них в промпте как <Picture 1>, "
                "<Picture 2>, <Picture 3> — по порядку приложения. Не описывай их заново."),
    "qwen21": ("\n\nКартинок несколько: ссылайся на них как the first reference image, "
               "the second reference image — по порядку приложения."),
}


def _agent_prepare(port: int, brief: str, pics: list[str], model_id: str, skill_id: str,
                   think: bool, mode: str, two_pass: bool = True, emit=None):
    """System + сообщения для агента. Сначала отдельный проход «опиши картинки»."""
    skill = skill_id or SKILL_FOR.get(model_id, "")
    system = skill_text(skill) or "Ты пишешь точные промпты для генерации изображений."
    system += AGENT_RULES + AGENT_INTENT.get(mode, "")
    if len(pics) > 1:
        system += MULTI_HINT.get(model_id, MULTI_HINT["qwen21"])

    description = ""
    if pics and two_pass:
        if emit:
            emit({"type": "status",
                  "text": "читаю картинку" if len(pics) == 1 else "читаю картинки"})
        ask = ("Опиши это изображение для дальнейшей работы." if len(pics) == 1 else
               "Опиши каждую картинку кратко: 2–3 предложения на картинку — главный объект, "
               "стиль, фон, свет. Без перечисления мелких деталей.")
        content = [{"type": "text", "text": ask}]
        content += [{"type": "image_url", "image_url": {"url": p}} for p in pics]
        description = _agent_chat(port, [
            {"role": "system", "content": AGENT_VISION},
            {"role": "user", "content": content},
        ], max_tokens=400 if len(pics) == 1 else min(700, 350 * len(pics)),
           think=think).strip()

    if description:
        what = "исходной картинки" if len(pics) == 1 else "исходных картинок"
        user_text = (f"Описание {what} (наблюдение):\n{description}\n\n"
                     f"Задача пользователя: {brief or 'сделай изображение по этому описанию'}")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user_text}]
    elif pics:
        content = [{"type": "text",
                    "text": brief or "сделай изображение по этим картинкам"}]
        content += [{"type": "image_url", "image_url": {"url": p}} for p in pics]
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": content}]
    else:
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": brief}]
    return skill, messages, description


def agent_prompt(model_id: str, brief: str, image_data: str = "", skill_id: str = "",
                 two_pass: bool = True, think: bool = False, mode: str = "",
                 images: list[str] | None = None) -> dict:
    brief = (brief or "").strip()
    pics = [p for p in (images if images is not None else ([image_data] if image_data else [])) if p]
    if not brief and not pics:
        raise ValueError("напишите, что нужно")
    info = agent_start()
    if not info.get("running"):
        raise RuntimeError(info.get("error") or "агент не запущен")
    port = info["port"]

    skill, messages, description = _agent_prepare(
        port, brief, pics, model_id, skill_id, think, mode, two_pass)

    text = _agent_chat(port, messages, max_tokens=900, think=think)
    prompt, aspect = parse_agent_reply(text)
    retried = False
    if not _looks_like_prompt(prompt):
        # один повтор: модель иногда отвечает рассуждением или по-русски
        retried = True
        messages = messages + [
            {"role": "assistant", "content": text[:2000]},
            {"role": "user", "content": "Ответ неверный: нужен только английский промпт "
                                        "в блоке ```prompt``` и строка формата. Повтори."},
        ]
        text = _agent_chat(port, messages, max_tokens=900, think=think)
        prompt, aspect = parse_agent_reply(text)
    if not prompt:
        raise RuntimeError("агент вернул пустой ответ")
    return {"prompt": prompt, "aspect": aspect, "skill": skill,
            "model": model_id, "description": description, "retried": retried, "raw": text}


def export_frames(prompt_id: str) -> dict:
    """Скопировать кадры прогона в свою папку — редактор читает только файлы."""
    st = job_status(prompt_id)
    imgs = [o for o in st.get("outputs") or [] if o["kind"] == "image"]
    frames = [o for o in imgs if o["node"] == "17"] or imgs
    if not frames:
        raise ValueError("в этом прогоне нет кадров")
    meta = st.get("meta") or {}
    parts = str(frames[0].get("subfolder") or "").replace("\\", "/").split("/")
    slug = meta.get("slug") or (parts[1] if len(parts) > 1 else "sprite")
    run = parts[2] if len(parts) > 2 and parts[2] else time.strftime("%Y%m%d-%H%M%S")
    target = ROOT / ".frames" / f"{slug}-{run}"
    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for i, o in enumerate(frames, 1):
        params = urllib.parse.urlencode({
            "filename": o["filename"], "subfolder": o["subfolder"], "type": o["type"],
        })
        with urllib.request.urlopen(COMFY + "/view?" + params, timeout=120) as r:
            data = r.read()
        if i == 1 and not data.startswith(b"\x89PNG"):
            raise ValueError("ComfyUI вернул не PNG")
        (target / f"{i:04d}.png").write_bytes(data)
        written += 1
    return {"dir": str(target), "count": written, "slug": slug, "run": run}


# -------------------------------------------------------------------- сервер

def stop_agent_for_memory() -> bool:
    """Перед генерацией гасим агента: он держит ~9 ГБ, а ComfyUI нужно больше.

    Пользователь всегда может снова нажать «Промпт агентом» — агент поднимется.
    """
    proc = _agent_state.get("proc")
    if proc is None and not _agent_alive(AGENT_PORT):
        return False
    try:
        agent_stop()
        print("[gen] агент остановлен, чтобы освободить память")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[gen] не удалось остановить агента: {exc}")
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "SpriteAnimStudio/0.1"
    protocol_version = "HTTP/1.1"

    # -- утилиты
    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8",
              extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _bad(self, msg: str, code: int = 400):
        self._json({"error": msg}, code)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _raw_body(self, limit: int = 20 * 1024 * 1024) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("слишком большой запрос")
        return self.rfile.read(n) if n else b""

    def log_message(self, fmt, *args):  # тише в консоли
        if "/api/job" in (self.path or ""):
            return
        sys.stdout.write("[http] " + (fmt % args) + "\n")

    # -- GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (UI_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/static/"):
                f = UI_DIR / u.path[len("/static/"):]
                if f.is_file():
                    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                    return self._send(200, f.read_bytes(), ctype)
                return self._bad("нет файла", 404)
            if u.path == "/api/state":
                return self._state()
            if u.path == "/api/net":
                return self._json(net_info())
            if u.path == "/api/android/update":
                return self._json(android_update())
            if u.path == "/api/android/apk":
                apk = android_apk_path()
                if apk is None:
                    return self._bad("APK не найден", 404)
                return self._serve_path(apk, "application/vnd.android.package-archive", apk.name)
            if u.path == "/api/firewall":
                return self._json(firewall_status())
            if u.path == "/api/comfy/owned":
                return self._json({**comfy_owned(), "running": comfy_online()})
            if u.path == "/api/agent":
                port = AGENT_PORT if _agent_alive(AGENT_PORT) else 0
                return self._json(agent_info(port, bool(_agent_state.get("proc") and port)))
            if u.path == "/api/graph":
                return self._graph_preview(q)
            if u.path == "/api/job":
                return self._json(job_status(q.get("id", [""])[0]))
            if u.path == "/api/progress/stream":
                return self._progress_stream((q.get("id") or [""])[0])
            if u.path == "/api/runs":
                try:
                    limit = max(1, min(200, int((q.get("limit") or ["60"])[0])))
                except ValueError:
                    limit = 60
                return self._json({"runs": runs_list(limit, (q.get("kind") or [""])[0])})
            if u.path == "/api/jobs":
                return self._json({"jobs": jobs_active()})
            if u.path == "/api/settings":
                return self._json(settings_info())
            if u.path == "/api/version":
                return self._json({"version": APP_VERSION, "repo": GITHUB_REPO})
            if u.path == "/api/update":
                return self._json(update_check(force=bool(q.get("force"))))
            if u.path == "/api/setup":
                return self._json(setup_status())
            if u.path == "/api/setup/progress":
                return self._json(setup_progress())
            if u.path == "/api/voice":
                return self._json(voice_status())
            if u.path in ("/sheet", "/sheet/"):
                return self._send(200, SHEET_UI.read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/sheet/api/"):
                return self._sheet_get(u.path[len("/sheet/api/"):], q)
            if u.path == "/api/fs/dirs":
                raw = (q.get("path") or [""])[0]
                return self._json(list_dirs(urllib.parse.unquote(raw)))
            if u.path == "/api/file":
                return self._proxy_view(q)
            if u.path == "/api/upscale/sources":
                return self._json({"sources": upscale_sources()})
            if u.path == "/api/upscale/results":
                return self._json({"results": upscale_results()})
            if u.path == "/api/sheets":
                return self._json({"sheets": sheets_list()})
            if u.path == "/api/output/file":
                raw = urllib.parse.unquote((q.get("path") or [""])[0])
                try:
                    data, ctype = output_file(raw)
                except ValueError as exc:
                    return self._bad(str(exc), 404)
                return self._send(200, data, ctype)
            if u.path == "/api/zip":
                return self._zip(q)
            return self._bad("неизвестный адрес", 404)
        except urllib.error.HTTPError as exc:
            return self._bad(f"ComfyUI ответил {exc.code}: {exc.read()[:400].decode('utf-8', 'replace')}", 502)
        except Exception as exc:  # noqa: BLE001
            return self._bad(f"{type(exc).__name__}: {exc}", 500)

    # -- POST
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/api/generate":
                return self._generate()
            if u.path == "/api/bg":
                return self._bg()
            if u.path == "/api/image/generate":
                return self._image_generate()
            if u.path == "/api/agent/start":
                return self._json(agent_start(wait=False))
            if u.path == "/api/agent/stop":
                return self._json(agent_stop())
            if u.path == "/api/translate":
                body = self._body()
                try:
                    return self._json({"text": translate_text(str(body.get("text") or ""))})
                except ValueError as exc:
                    return self._bad(str(exc), 422)
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/translate/stream":
                return self._translate_stream()
            if u.path == "/api/quit":
                threading.Timer(0.6, shutdown_app).start()
                return self._json({"ok": True})
            if u.path == "/api/runs":
                body = self._body()
                try:
                    return self._json(runs_add(body))
                except RuntimeError as exc:
                    return self._bad(str(exc), 500)
            if u.path == "/api/jobs/done":
                body = self._body()
                jobs_remove(str(body.get("id") or ""))
                return self._json({"ok": True})
            if u.path == "/api/settings":
                body = self._body()
                try:
                    return self._json(apply_settings(body))
                except ValueError as exc:
                    return self._bad(str(exc), 422)
                except RuntimeError as exc:
                    return self._bad(str(exc), 500)
            if u.path == "/api/update/install":
                try:
                    return self._json(update_install())
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/upscale":
                try:
                    return self._json(upscale_start(self._body()))
                except ValueError as exc:
                    return self._bad(str(exc), 422)
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/sheet/save":
                try:
                    blob = self._raw_body(limit=120 * 1024 * 1024)
                    return self._json(save_sheet(
                        urllib.parse.unquote((q.get("name") or [""])[0]),
                        blob,
                        int((q.get("cols") or ["0"])[0] or 0),
                        int((q.get("rows") or ["0"])[0] or 0),
                        int((q.get("cw") or ["0"])[0] or 0),
                        int((q.get("ch") or ["0"])[0] or 0),
                        int((q.get("count") or ["0"])[0] or 0),
                        (q.get("crop") or [""])[0],
                        (q.get("src") or [""])[0],
                        (q.get("origin") or [""])[0],
                        (q.get("pad") or [""])[0],
                        (q.get("pivot") or [""])[0],
                    ))
                except ValueError as exc:
                    return self._bad(str(exc), 422)
                except Exception as exc:  # noqa: BLE001
                    return self._bad("не удалось сохранить лист: " + str(exc), 500)
            if u.path == "/api/sheet/preview":
                try:
                    blob = self._raw_body(limit=20 * 1024 * 1024)
                    return self._json(save_sheet_preview(
                        urllib.parse.unquote((q.get("dir") or [""])[0]), blob))
                except ValueError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/fs/dirs":
                raw = (q.get("path") or [""])[0]
                return self._json(list_dirs(urllib.parse.unquote(raw)))
            if u.path == "/api/setup/download":
                body = self._body()
                try:
                    return self._json(download_group(str(body.get("group") or "")))
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/setup/cancel":
                return self._json(cancel_download())
            if u.path.startswith("/sheet/api/"):
                return self._sheet_post(u.path[len("/sheet/api/"):], q)
            if u.path == "/api/voice":
                try:
                    pcm = self._raw_body()
                except ValueError as exc:
                    return self._bad(str(exc), 413)
                try:
                    return self._json(voice_transcribe(pcm))
                except ValueError as exc:
                    return self._bad(str(exc), 422)
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
                except Exception as exc:  # noqa: BLE001
                    return self._bad(f"распознавание не удалось: {exc}", 500)
            if u.path == "/api/setup/comfy/install":
                try:
                    return self._json(comfy_install())
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/setup/comfy/run":
                try:
                    return self._json(comfy_run_portable())
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/comfy/start":
                try:
                    return self._json(comfy_start())
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/comfy/stop":
                try:
                    return self._json(comfy_stop())
                except RuntimeError as exc:
                    return self._bad(str(exc), 409)
            if u.path == "/api/firewall/open":
                try:
                    return self._json(firewall_open())
                except RuntimeError as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/comfy/pick":
                path = sheet_dialog("comfy", "")
                if not path:
                    return self._json({"ok": False})
                p = Path(path)
                if not p.is_file():
                    return self._bad("файл не найден", 422)
                with _settings_lock:
                    _settings["comfy_cmd"] = str(p)
                    _save_settings()
                _launcher_cache["t"] = 0.0
                return self._json({"ok": True, "path": str(p), "settings": settings_info()})
            if u.path == "/api/settings/open":
                if not hasattr(os, "startfile"):
                    return self._bad("открыть папку можно только в Windows", 422)
                raw = urllib.parse.unquote((q.get("path") or [""])[0])
                target = output_dir()
                if raw:
                    try:
                        target = (output_dir().resolve() / raw).resolve()
                        target.relative_to(output_dir().resolve())
                    except (ValueError, OSError):
                        return self._bad("папка должна лежать внутри output", 422)
                    if not target.is_dir():
                        return self._bad("папка не найдена", 404)
                try:
                    os.startfile(str(target))
                    return self._json({"ok": True})
                except Exception as exc:  # noqa: BLE001
                    return self._bad(str(exc), 500)
            if u.path == "/api/agent/prompt":
                body = self._body()
                try:
                    imgs = body.get("images")
                    return self._json(agent_prompt(
                        str(body.get("model") or ""), str(body.get("brief") or ""),
                        str(body.get("image") or ""), str(body.get("skill") or ""),
                        bool(body.get("two_pass", True)), bool(body.get("think")),
                        str(body.get("mode") or ""),
                        [str(i) for i in imgs] if isinstance(imgs, list) else None))
                except (ValueError, RuntimeError) as exc:
                    return self._bad(str(exc), 422)
            if u.path == "/api/agent/prompt/stream":
                return self._agent_stream()
            if u.path == "/api/frames":
                body = self._body()
                pid = str(body.get("id") or "")
                if not pid:
                    return self._bad("нужен id прогона", 422)
                return self._json(export_frames(pid))
            if u.path == "/api/prompt":
                body = self._body()
                color = str(body.get("color") or "magenta")
                final, added, conflict = normalize_prompt(str(body.get("text") or ""), color)
                return self._json({
                    "final": final,
                    "added": added,
                    "conflict": conflict,
                    "bg": bg_clause(color if color in COLOR_WORDS else "magenta"),
                    "tech": TECH_TAIL,
                })
            if u.path == "/api/stop":
                body = self._body()
                pid = body.get("id") or ""
                with _UPSCALE_LOCK:
                    event = _UPSCALE_CANCEL.get(str(pid))
                if event is not None:
                    event.set()
                    return self._json({"ok": True})
                try:
                    comfy_json("/interrupt", {"prompt_id": pid}, timeout=10)
                except Exception:
                    comfy_json("/interrupt", {}, timeout=10)
                return self._json({"ok": True})
            return self._bad("неизвестный адрес", 404)
        except Exception as exc:  # noqa: BLE001
            return self._bad(f"{type(exc).__name__}: {exc}", 500)

    # -- реализация
    def _state(self):
        online = comfy_online()
        modes = load_workflows()
        q = {}
        bg = {"nodes": False, "unet": "", "clip": "", "vae": "", "prompt": BG_PROMPT}
        if online:
            try:
                bg.update(bg_models(object_info()))
            except Exception:
                pass
        if online:
            try:
                q = comfy_json("/queue", timeout=5)
            except Exception:
                q = {}
        if online and not _settings.get("comfy_cmdline"):
            threading.Thread(target=comfy_capture, daemon=True).start()
        self._json({
            "comfy": {
                "online": online,
                "version": comfy_version() if online else "",
                "running": len(q.get("queue_running") or []),
                "pending": len(q.get("queue_pending") or []),
                "cmd": comfy_launcher_path(),
                "remembered": bool(_settings.get("comfy_cmdline")),
                "owned": bool(_settings.get("comfy_owned")),
                "auto": bool(_settings.get("comfy_auto")),
            },
            "modes": modes,
            "bg": bg,
            "upscale": {"model": upscale_model_available() if online else ""},
            "image": {"models": image_models(object_info())} if online else {"models": []},
        })

    def _graph_preview(self, q):
        mode = (q.get("mode") or ["walk"])[0]
        path, manifest = find_workflow(mode)
        if not path:
            return self._bad("нет такого воркфлоу", 404)
        params = {
            "prompt": (q.get("prompt") or [""])[0] or None,
            "width": (q.get("width") or [""])[0] or None,
            "height": (q.get("height") or [""])[0] or None,
            "seconds": (q.get("seconds") or [""])[0] or None,
            "seed": (q.get("seed") or [""])[0] or None,
            "steps": (q.get("steps") or [""])[0] or None,
        }
        params = {k: v for k, v in params.items() if v}
        graph, extra = build_graph(manifest, params, object_info(), _run_id())
        self._json({"graph": graph, **extra, "manifest": manifest})

    def _generate(self):
        body = self._body()
        stop_agent_for_memory()
        mode = str(body.get("mode") or "")
        path, manifest = find_workflow(mode)
        if not path:
            return self._bad("выберите тип анимации", 422)
        image = body.get("image") or {}
        if not image.get("data"):
            return self._bad("нужна картинка персонажа", 422)

        run = _run_id()
        blob = base64.b64decode(image["data"].split(",")[-1])
        uploaded = upload_image(image.get("name") or "character.png", blob)

        graph, extra = build_graph(manifest, body, object_info(), run)
        for _, n in _node_by_class(graph, "LoadImage"):
            n["inputs"]["image"] = uploaded

        if body.get("dry"):  # проверка сборки без запуска на видеокарте
            return self._json({"dry": True, "uploaded": uploaded, "run": run,
                               "graph": graph, **extra})

        cid = uuid.uuid4().hex
        res = comfy_json("/prompt", {"prompt": graph, "client_id": cid,
                                     "extra_data": {"preview_method": "latent2rgb"}}, timeout=60)
        if res.get("error"):
            return self._bad(str(res.get("error")) + " " + json.dumps(res.get("node_errors") or {}, ensure_ascii=False), 422)
        start_progress(str(res.get("prompt_id") or ""), cid, graph)
        h3 = next(v for v in graph.values() if v["class_type"] == "MiniMaxH3ImageToVideo")["inputs"]
        seed = next((v["inputs"].get("noise_seed") for v in graph.values()
                     if v["class_type"] == "RandomNoise"), None)
        jobs_add({"id": res.get("prompt_id"), "kind": "anim", "ts": time.time(),
                  "mode": manifest["mode"], "name": body.get("name") or "",
                  "prompt": body.get("prompt") or "", "steps": int(body.get("steps") or 20),
                  "seed": seed, "frames": h3["length"],
                  "width": h3["width"], "height": h3["height"]})
        self._json({
            "id": res.get("prompt_id"),
            "run": run,
            "mode": manifest["mode"],
            "width": h3["width"],
            "height": h3["height"],
            "length": h3["length"],
            "seed": seed,
            **extra,
        })

    def _bg(self):
        body = self._body()
        stop_agent_for_memory()
        image = body.get("image") or {}
        if not image.get("data"):
            return self._bad("нужна картинка", 422)
        info = object_info()
        models = bg_models(info)
        if not models["nodes"] or not (models["unet"] and models["clip"] and models["vae"]):
            return self._bad("не хватает моделей или нод Qwen Image 2.1: "
                             + json.dumps({k: v for k, v in models.items()}, ensure_ascii=False), 422)
        run = _run_id()
        blob = base64.b64decode(image["data"].split(",")[-1])
        uploaded = upload_image(image.get("name") or "source.png", blob)
        prompt = str(body.get("prompt") or BG_PROMPT).strip() or BG_PROMPT
        raw = body.get("resolution")
        try:
            resolution = int(raw) if raw not in (None, "") else 1024
        except (TypeError, ValueError):
            resolution = 1024
        seed = int(body.get("seed") or 0) or random.randrange(1, 2 ** 50)
        graph = build_bg_graph(uploaded, prompt, resolution, seed, run, models)
        cid = uuid.uuid4().hex
        res = comfy_json("/prompt", {"prompt": graph, "client_id": cid,
                                     "extra_data": {"preview_method": "latent2rgb"}}, timeout=60)
        if res.get("error"):
            return self._bad(str(res.get("error")) + " "
                             + json.dumps(res.get("node_errors") or {}, ensure_ascii=False), 422)
        start_progress(str(res.get("prompt_id") or ""), cid, graph)
        jobs_add({"id": res.get("prompt_id"), "kind": "bg", "ts": time.time(),
                  "prompt": prompt, "resolution": graph["474"]["inputs"]["resolution"],
                  "seed": seed})
        self._json({"id": res.get("prompt_id"), "run": run, "seed": seed,
                    "resolution": graph["474"]["inputs"]["resolution"]})

    def _progress_stream(self, pid: str):
        """SSE с прогрессом задания: шаг/всего, подпись ноды и превью кадра."""
        if not pid:
            return self._bad("нужен id задания", 422)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            for _ in range(40):                 # ждём, пока монитор увидит задание
                if progress_snapshot(pid):
                    break
                time.sleep(0.25)
            if not progress_snapshot(pid):
                emit({"state": "unavailable"})
                return
            last = None
            deadline = time.time() + 3600
            while time.time() < deadline:
                st = progress_snapshot(pid)
                payload = {k: st[k] for k in ("state", "label", "step", "total", "node", "error")
                           if st.get(k) is not None}
                if st.get("preview"):
                    payload["preview"] = st["preview"]
                key = (payload.get("state"), payload.get("label"), payload.get("step"),
                       payload.get("total"), payload.get("error"), len(st.get("preview") or ""))
                if key != last:
                    emit(payload)
                    last = key
                if st.get("state") in ("done", "error"):
                    break
                time.sleep(0.3)
            emit({"state": "closed"})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _sse_begin(self):
        """Открыть SSE-поток и вернуть emit(obj): событие сразу уходит клиенту."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        return emit

    def _agent_stream(self):
        """Тот же агент, но ответ идёт кусками (SSE): текст появляется по мере генерации."""
        body = self._body()
        brief = str(body.get("brief") or "").strip()
        image_data = str(body.get("image") or "")
        model_id = str(body.get("model") or "")
        skill_id = str(body.get("skill") or "")
        think = bool(body.get("think"))
        mode = str(body.get("mode") or "")
        imgs = body.get("images")
        pics = [str(i) for i in imgs] if isinstance(imgs, list) else (
            [image_data] if image_data else [])
        pics = [p for p in pics if p]
        if not brief and not pics:
            return self._bad("напишите, что нужно", 422)

        emit = self._sse_begin()

        try:
            emit({"type": "status", "text": "запускаю агента"})
            info = agent_start()
            if not info.get("running"):
                emit({"type": "error", "message": info.get("error") or "агент не запущен"})
                return
            port = info["port"]
            skill, messages, description = _agent_prepare(
                port, brief, pics, model_id, skill_id, think, mode, emit=emit)
            if description:
                emit({"type": "description", "text": description})

            emit({"type": "status", "text": "пишу промпт"})
            text = _agent_chat_stream(port, messages,
                                      lambda d: emit({"type": "delta", "text": d}),
                                      max_tokens=900, think=think)
            prompt, aspect = parse_agent_reply(text)
            retried = False
            if not _looks_like_prompt(prompt):
                retried = True
                emit({"type": "status", "text": "уточняю ответ"})
                retry_messages = messages + [
                    {"role": "assistant", "content": text[:2000]},
                    {"role": "user", "content": "Ответ неверный: нужен только английский промпт "
                                                "в блоке ```prompt``` и строка формата. Повтори."},
                ]
                text = _agent_chat(port, retry_messages, max_tokens=900, think=think)
                prompt, aspect = parse_agent_reply(text)
            if not prompt:
                emit({"type": "error", "message": "агент вернул пустой ответ"})
                return
            emit({"type": "done", "prompt": prompt, "aspect": aspect, "skill": skill,
                  "description": description, "retried": retried})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return  # пользователь нажал «Стоп» или закрыл страницу
        except Exception as exc:  # noqa: BLE001
            try:
                emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass

    def _translate_stream(self):
        """Перевод на русский кусками: видно, что агент работает, можно отменить."""
        body = self._body()
        text = str(body.get("text") or "").strip()
        if not text:
            return self._bad("пустой текст", 422)
        text = text[:4000]

        emit = self._sse_begin()
        try:
            emit({"type": "status", "text": "запускаю агента"})
            info = agent_start()
            if not info.get("running"):
                emit({"type": "error", "message": info.get("error") or "агент не запущен"})
                return
            emit({"type": "status", "text": "перевожу"})
            out = _translate_clean(_agent_chat_stream(
                info["port"], translate_messages(text),
                lambda d: emit({"type": "delta", "text": d}),
                max_tokens=translate_max_tokens(text), think=False))
            if not out:
                emit({"type": "error", "message": "агент не вернул перевод"})
                return
            emit({"type": "done", "text": out})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return  # пользователь нажал «RU» ещё раз или закрыл страницу
        except Exception as exc:  # noqa: BLE001
            try:
                emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass

    def _image_generate(self):
        body = self._body()
        stop_agent_for_memory()
        prompt = str(body.get("prompt") or "").strip()
        if not prompt:
            return self._bad("напишите промпт", 422)
        info = object_info()
        model_id = str(body.get("model") or IMAGE_MODELS[0]["id"])
        model = next((m for m in image_models(info) if m["id"] == model_id), None)
        if not model:
            return self._bad("неизвестная модель", 422)
        if not model["ready"]:
            return self._bad("не хватает: " + ", ".join(model["missing"]), 422)
        width, height = image_size(int(body.get("base") or 1024), str(body.get("aspect") or "1:1"))
        seed = int(body.get("seed") or 0) or random.randrange(1, 2 ** 50)
        steps = max(2, min(80, int(body.get("steps") or model["steps"])))
        cfg = float(body.get("cfg") or model["cfg"])
        enhance = bool(body.get("enhance")) and bool(model.get("enhancer"))
        refs_in = body.get("refs")
        if not isinstance(refs_in, list):
            legacy = str(body.get("ref") or "")
            refs_in = [legacy] if legacy else []
        refs_in = [r for r in refs_in if isinstance(r, str) and r][:8]
        ref_mode = str(body.get("ref_mode") or "off")
        # Картинки подключаем ТОЛЬКО когда явно выбрано «Изменить это»: иначе модель
        # рисует с нуля по промпту (так результат заметно лучше и персонаж не «переезжает»).
        use_ref = bool(refs_in) and ref_mode == "edit" and bool(model.get("ref"))
        ref_names = []
        if use_ref:
            for i, data in enumerate(refs_in, 1):
                ref_names.append(upload_image(f"ref_{i}.png",
                                              base64.b64decode(data.split(",")[-1])))
        run = _run_id()
        graph = build_image_graph(model, prompt, str(body.get("negative") or ""),
                                  width, height, seed, steps, cfg, run,
                                  enhance, model.get("enhancer") or "", refs=ref_names)
        cid = uuid.uuid4().hex
        res = comfy_json("/prompt", {"prompt": graph, "client_id": cid,
                                     "extra_data": {"preview_method": "latent2rgb"}}, timeout=60)
        if res.get("error"):
            return self._bad(str(res.get("error")) + " "
                             + json.dumps(res.get("node_errors") or {}, ensure_ascii=False), 422)
        start_progress(str(res.get("prompt_id") or ""), cid, graph)
        jobs_add({"id": res.get("prompt_id"), "kind": "img", "ts": time.time(),
                  "model": model["id"], "prompt": prompt, "width": width, "height": height,
                  "base": int(body.get("base") or 1024), "aspect": str(body.get("aspect") or "1:1"),
                  "steps": steps, "seed": seed, "ref": bool(ref_names), "refs": len(ref_names),
                  "ref_mode": ref_mode})
        self._json({"id": res.get("prompt_id"), "run": run, "model": model["id"],
                    "width": width, "height": height, "seed": seed, "steps": steps, "cfg": cfg,
                    "enhanced": enhance, "ref": bool(ref_names), "refs": len(ref_names)})

    def _proxy_view(self, q):
        filename = (q.get("filename") or [""])[0]
        subfolder = (q.get("subfolder") or [""])[0]
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": (q.get("type") or ["output"])[0],
        })
        try:
            r = urllib.request.urlopen(COMFY + "/view?" + params, timeout=120)
        except Exception:  # noqa: BLE001 — ComfyUI мог почистить output
            r = None
        if r is not None:
            with r:
                ctype = r.headers.get("Content-Type") or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                length = r.headers.get("Content-Length")
                if length:
                    self.send_header("Content-Length", length)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return
        # Наша копия в output/ — чтобы история и превью жили без файлов ComfyUI.
        group, run, tail = output_location(subfolder)
        base = output_dir() / group / run
        candidates = [base.joinpath(*tail, filename) if tail else base / filename,
                      base / filename]           # старые копии лежали без подпапок
        for local in candidates:
            if local.is_file():
                ctype = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
                return self._send(200, local.read_bytes(), ctype)
        return self._bad("нет файла", 404)

    def _sheet_file(self, directory: str, name: str):
        core = sheet_core()
        file = (Path(directory or "").resolve() / Path(str(name or "")).name)
        if not core.IMAGES.search(file.name) or not file.is_file():
            return self._bad("not found", 404)
        ctype = core.TYPES.get(file.suffix[1:].lower(), "application/octet-stream")
        return self._serve_path(file, ctype)

    def _serve_path(self, file: Path, ctype: str, download: str = ""):
        size = file.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range") or ""
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if m and (m.group(1) or m.group(2)):
            status = 206
            if m.group(1):
                start = int(m.group(1))
            if m.group(2):
                end = int(m.group(2))
        end = min(end, size - 1)
        length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            self.send_header("Content-Disposition",
                             f'attachment; filename="{download}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with file.open("rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(1 << 16, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)
        return None

    def _sheet_get(self, action: str, q):
        core = sheet_core()
        core._state["lang"] = "en" if (self.headers.get("X-Lang") or "").lower() == "en" else "ru"
        get = lambda key: (q.get(key) or [""])[0]  # noqa: E731

        def need():
            if not core.project():
                raise core.Fail("noProject", 409)

        try:
            if action == "state":
                cfg = core._state["config"]
                recent = [r for r in (cfg.get("recent") or []) if (Path(r) / "project.godot").is_file()]
                return self._json({"api": core.API, "project": core.describe(),
                                   "recent": recent, "godot": core.find_godot()})
            if action == "refresh":
                need()
                return self._json({"ok": True, "project": core.describe()})
            if action == "unity/assets":
                need()
                return self._json({"ok": True, **core.unity_assets()})
            if action == "list":
                return self._json(core.list_dir(get("dir")))
            if action == "exists":
                need()
                return self._json({"exists": core.sheet_target(get("dir"), get("name")).is_file()})
            if action == "file":
                return self._sheet_file(get("dir"), get("name"))
            return self._bad("неизвестный адрес", 404)
        except core.Fail as exc:
            return self._bad(str(exc), exc.code)
        except Exception as exc:  # noqa: BLE001
            return self._bad(f"{type(exc).__name__}: {exc}", 500)

    def _sheet_post(self, action: str, q):
        core = sheet_core()
        core._state["lang"] = "en" if (self.headers.get("X-Lang") or "").lower() == "en" else "ru"
        qd = {key: values[0] for key, values in q.items()}
        get = lambda key: qd.get(key, "")  # noqa: E731
        try:
            if action == "project":
                return self._json({"ok": True, "project": core.open_project(get("path"))})
            if action == "pick":
                start = get("start") or (core._state["config"].get("godot") if get("kind") == "godot" else "")
                return self._json({"path": sheet_dialog(get("kind"), start)})
            if action == "godot":
                exe = get("path").strip('"')
                if not Path(exe).is_file() or not exe.lower().endswith(".exe"):
                    raise core.Fail("noGodot")
                core._state["config"]["godot"] = exe
                core.save_config()
                return self._json({"ok": True, "godot": exe})
            if action == "ping" or action == "bye":
                return self._json({"ok": True})
            if action in ("save", "install", "remove", "undo"):
                if not core.project():
                    raise core.Fail("noProject", 409)
                png = self._raw_body(limit=300 * 1024 * 1024) if action in ("save", "install") else b""
                if action == "save":
                    if core.project().get("engine") == "unity":
                        return self._json(core.save_unity(qd, png))
                    return self._json(core.save_godot(qd, png))
                if action == "install":
                    if core.project().get("engine") == "unity":
                        return self._json(core.install_unity(qd, png))
                    return self._json(core.install_godot(qd, png))
                if action == "remove":
                    return self._json(core.remove_anim(qd))
                return self._json({"ok": True, "label": core.undo()})
            return self._bad("неизвестный адрес", 404)
        except core.Fail as exc:
            return self._bad(str(exc), exc.code)
        except ValueError as exc:
            return self._bad(str(exc), 422)
        except Exception as exc:  # noqa: BLE001
            return self._bad(f"{type(exc).__name__}: {exc}", 500)

    def _zip(self, q):
        pid = (q.get("id") or [""])[0]
        st = job_status(pid)
        imgs = [o for o in st.get("outputs") or [] if o["kind"] == "image"]
        # #17 — PNG с прозрачностью; если его нет, отдаём то, что есть.
        frames = [o for o in imgs if o["node"] == "17"] or imgs
        if not frames:
            return self._bad("кадров пока нет", 404)
        # #17 — PNG с прозрачностью, #15 — кадры на цветном фоне.
        frames.sort(key=lambda o: (o["node"] != "17", o["filename"]))
        name = q.get("name", ["sprite-frames"])[0]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for i, o in enumerate(frames, 1):
                params = urllib.parse.urlencode({
                    "filename": o["filename"], "subfolder": o["subfolder"], "type": o["type"],
                })
                with urllib.request.urlopen(COMFY + "/view?" + params, timeout=120) as r:
                    zf.writestr(f"{name}/{i:04d}{Path(o['filename']).suffix}", r.read())
        data = buf.getvalue()
        self._send(200, data, "application/zip", {
            "Content-Disposition": f'attachment; filename="{name}.zip"',
        })


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError)):
            return  # браузер закрыл соединение — это нормально
        super().handle_error(request, client_address)


def port_busy() -> bool:
    """На Windows SO_REUSEADDR позволяет двум процессам слушать один порт,
    поэтому занятость проверяем подключением, а не попыткой bind."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


# ------------------------------------------------------------ телефон / APK
DISCOVERY_MAGIC = b"SPRITEANIM-DISCOVER-1"


def android_dir() -> Path:
    """Папка с APK: рядом с исходниками или внутри сборки PyInstaller."""
    candidates = [ROOT / "android-apk"]
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(Path(meipass) / "android-apk")
    try:
        candidates.append(Path(sys.executable).resolve().parent / "android-apk")
    except OSError:
        pass
    for path in candidates:
        try:
            if path.is_dir():
                return path
        except OSError:
            continue
    return candidates[0]


def android_meta() -> dict:
    path = android_dir() / "version.json"
    try:
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def android_apk_path() -> Path | None:
    root = android_dir()
    meta = android_meta()
    link = str(meta.get("apk") or "")
    if link:
        name = Path(urllib.parse.urlparse(link).path).name
        cand = root / name
        if cand.is_file():
            return cand
    found = sorted(root.glob("*.apk"))
    return found[-1] if found else None


def android_update() -> dict:
    """Последняя версия телефона из android-apk/version.json."""
    out = dict(android_meta())
    apk = android_apk_path()
    out.setdefault("versionCode", 0)
    out.setdefault("versionName", "")
    if apk is not None:
        out["apk_local"] = "/api/android/apk"
        out["apk_size"] = apk.stat().st_size
        out["apk_name"] = apk.name
    return out


def firewall_rules() -> list[tuple[str, str]]:
    return [("SpriteAnim Studio (TCP 8189)", "8189"),
            ("SpriteAnim Studio (UDP 8190)", str(LAN_PORT))]


def firewall_status() -> dict:
    if os.name != "nt":
        return {"available": False, "open": False}
    opened = 0
    for name, _ in firewall_rules():
        try:
            r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=10, creationflags=0x08000000)
            if r.returncode == 0:
                opened += 1
        except Exception:  # noqa: BLE001
            pass
    return {"available": True, "open": opened == len(firewall_rules()),
            "rules": opened, "total": len(firewall_rules()), "lan": lan_enabled()}


def firewall_open() -> dict:
    """Добавляет правила брандмауэра для TCP 8189 и UDP 8190 (нужен UAC)."""
    if os.name != "nt":
        raise RuntimeError("брандмауэр доступен только в Windows")
    script = Path(tempfile.gettempdir()) / "spriteanim-firewall.bat"
    lines = ["@echo off"]
    for name, port in firewall_rules():
        proto = "UDP" if "UDP" in name else "TCP"
        lines.append(f'netsh advfirewall firewall delete rule name="{name}" >nul 2>&1')
        lines.append(f'netsh advfirewall firewall add rule name="{name}" dir=in action=allow '
                     f'protocol={proto} localport={port} profile=any remoteip=localsubnet')
    try:
        script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        ps = f"Start-Process -FilePath '{script}' -Verb RunAs -Wait"
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, creationflags=0x08000000)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"не удалось открыть брандмауэр: {exc}") from exc
    return {"ok": True, "elevated": True}


def discovery_loop(stop: threading.Event) -> None:
    """UDP-поиск студии телефоном: ответ на SPRITEANIM-DISCOVER-1."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", LAN_PORT))
        sock.settimeout(1.0)
    except OSError as exc:
        print(f"[discovery] UDP {LAN_PORT}: {exc}")
        return
    payload = json.dumps(net_info(), ensure_ascii=False).encode("utf-8")
    print(f"[discovery] слушаю UDP {LAN_PORT}")
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        except OSError:
            break
        if data.strip().startswith(DISCOVERY_MAGIC):
            try:
                sock.sendto(payload, addr)
            except OSError:
                pass
    try:
        sock.close()
    except OSError:
        pass


def serve():
    if not (UI_DIR / "index.html").is_file():
        print("!! нет ui/index.html")
        raise SystemExit(1)
    for sub in ("images", "background", "animation", "upscaled", "sheets"):
        try:
            (output_dir() / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    stale = upscale_recover()
    if stale:
        print(f"[upscale] помечено прерванных заданий: {stale}")
    import atexit
    atexit.register(_agent_quit)
    url = f"http://127.0.0.1:{PORT}"
    if port_busy():
        print(f"Уже запущено: {url}")
        if os.environ.get("SPRITE_NO_BROWSER") != "1":
            import webbrowser
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return
    bind = bind_host()
    try:
        httpd = Server((bind, PORT), Handler)
    except OSError as exc:
        print(f"Не удалось занять порт {PORT}: {exc}")
        return
    print(f"SpriteAnim Studio -> {url}")
    if lan_enabled():
        for lan_url in net_info().get("urls") or []:
            print(f"  телефон        -> {lan_url}")
        stop_discovery = threading.Event()
        threading.Thread(target=discovery_loop, args=(stop_discovery,),
                         daemon=True, name="discovery").start()
    print(f"ComfyUI         -> {COMFY}  ({'online' if comfy_online() else 'OFFLINE'})")
    if os.environ.get("SPRITE_NO_BROWSER") != "1":
        import webbrowser

        def open_later():
            time.sleep(1.0)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=open_later, daemon=True).start()
    httpd.serve_forever()


# -------------------------------------------------------------------- проверка

def check(against: str = ""):
    info = object_info()
    modes = load_workflows()
    print(f"ComfyUI: {'online' if comfy_online() else 'OFFLINE'} {comfy_version()}")
    print(f"workflows: {len(modes)}")
    graph = {}
    for m in modes:
        graph, extra = build_graph(m, {}, info, "check")
        print(f"  - {m['mode']:<8} {m['file']}  nodes: {len(graph)}  {m['width']}x{m['height']}  "
              f"{m['length']} frames  trim={m['trim_mode']}")
        for w in extra["warnings"]:
            print(f"      ! {w}")
        if extra["prompt_added"]:
            print(f"      + дописано в промпт: {len(extra['prompt_added'])} блок(а)")
        h3 = next(v for v in graph.values() if v["class_type"] == "MiniMaxH3ImageToVideo")
        for k, v in h3["inputs"].items():
            if isinstance(v, list) and v[0] not in graph:
                print(f"      ! link {k} -> #{v[0]} lost")
    if against:
        ref = json.loads(Path(against).read_text("utf-8"))
        ref = ref.get("graph") or ref
        print(f"\ncompare with {against}")
        print(f"  nodes: ours {len(graph)}, reference {len(ref)}")
        missing = sorted(set(map(str, ref)) - set(map(str, graph)), key=lambda s: int(s) if s.isdigit() else 0)
        extra = sorted(set(map(str, graph)) - set(map(str, ref)), key=lambda s: int(s) if s.isdigit() else 0)
        print(f"  missing: {missing or '-'}")
        print(f"  extra:   {extra or '-'}")
        diffs = 0
        for node_id in sorted(set(map(str, ref)) & set(map(str, graph)), key=lambda s: int(s)):
            a, b = ref[node_id], graph[node_id]
            if a["class_type"] != b["class_type"]:
                print(f"  #{node_id}: type {b['class_type']} vs {a['class_type']}")
                diffs += 1
                continue
            ka, kb = set(a["inputs"]), set(b["inputs"])
            if ka != kb:
                print(f"  #{node_id}: fields -{sorted(ka - kb)} +{sorted(kb - ka)}")
                diffs += 1
            for key in sorted(ka & kb):
                va, vb = a["inputs"][key], b["inputs"][key]
                if va != vb:
                    shown = (lambda x: (x[:70] + "...") if isinstance(x, str) and len(x) > 70 else x)
                    print(f"  #{node_id}.{key}: {shown(vb)!r} vs {shown(va)!r}")
                    diffs += 1
        print(f"  value differences: {diffs}")


if __name__ == "__main__":
    # pythonw.exe (запуск без консольного окна) не имеет stdout/stderr — print()
    # падал бы с AttributeError. Пишем всё в .cache/studio.log.
    if sys.executable.lower().endswith("pythonw.exe"):
        _log_dir = ROOT / ".cache"
        _log_dir.mkdir(exist_ok=True)
        _log_path = _log_dir / "studio.log"
        try:
            if _log_path.is_file() and _log_path.stat().st_size > 1_000_000:
                _log_path.replace(_log_dir / "studio.log.1")
        except OSError:
            pass
        _log = open(_log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = _log
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "--check" in sys.argv:
        i = sys.argv.index("--check")
        ref = ""
        if "--against" in sys.argv:
            ref = sys.argv[sys.argv.index("--against") + 1]
        check(ref)
    else:
        serve()
