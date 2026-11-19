"""Порт серверной части Sprite Sheet Maker (server.js) без Node.

Проекты Godot/Unity, поиск персонажей, сохранение листа, установка анимации,
удаление, бэкапы и отмена. Логика и тексты повторяют оригинал.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import data_fields
import godot_frames as frames
import unity

API = 5
IMAGES = re.compile(r"\.(png|jpe?g|webp|bmp|gif|mp4|webm|mov|m4v|mkv)$", re.I)
TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
    "bmp": "image/bmp", "gif": "image/gif", "mp4": "video/mp4", "m4v": "video/mp4",
    "webm": "video/webm", "mov": "video/quicktime", "mkv": "video/x-matroska",
}
ADAPTER = "sprite_sheet_maker.json"
DATA_VALUES = ["texture", "cols", "rows", "frames", "fps", "hit_frame", "stride",
               "sprite_scale", "sprite_foot", "sprite_top"]

EDITOR_SOURCE_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "assets" / "SpriteAnimStudio.cs",
    Path(__file__).resolve().parent.parent / "sheet" / "editor" / "SpriteAnimStudio.cs",
]


def editor_source() -> Path:
    return next((p for p in EDITOR_SOURCE_CANDIDATES if p.is_file()),
                EDITOR_SOURCE_CANDIDATES[0])


APP_DATA = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / "SpriteSheetMaker"
CONFIG_FILE = APP_DATA / "config.json"

TEXT = {
    "ru": {
        "noProject": "Сначала выберите папку игры",
        "notProject": "В этой папке нет project.godot (Godot 4) или ProjectSettings/ProjectVersion.txt (Unity)",
        "godot3": "Это проект Godot 3 — поддерживается только Godot 4",
        "badDir": "Папка должна быть внутри проекта",
        "badName": "Имя файла пустое",
        "exists": "Файл уже есть",
        "notPng": "Это не PNG",
        "noFolder": "Папка не найдена",
        "noGodot": "Не указан путь к Godot — выберите Godot.exe в окне «Игра»",
        "importFailed": "Godot не импортировал файл",
        "notFrames": "Этот файл не набор анимаций (SpriteFrames)",
        "noCharacter": "Такого персонажа нет — обновите список",
        "noAnim": "Не указано имя анимации",
        "nothingToUndo": "Отменять нечего",
        "notInUnity": "В Unity анимации удаляются в самом редакторе — здесь только установка",
        "unityPath": "Путь должен быть внутри Assets и указывать на .controller или .anim",
        "unityMissing": "Такого файла в проекте нет — обновите список",
    },
    "en": {
        "noProject": "Choose the game folder first",
        "notProject": "This folder has no project.godot (Godot 4) or ProjectSettings/ProjectVersion.txt (Unity)",
        "godot3": "This is a Godot 3 project — only Godot 4 is supported",
        "badDir": "The folder must be inside the project",
        "badName": "The file name is empty",
        "exists": "The file already exists",
        "notPng": "This is not a PNG",
        "noFolder": "Folder not found",
        "noGodot": "Godot path is not set — choose Godot.exe in the «Game» window",
        "importFailed": "Godot did not import the file",
        "notFrames": "This file is not an animation set (SpriteFrames)",
        "noCharacter": "No such character — refresh the list",
        "noAnim": "The animation name is missing",
        "nothingToUndo": "Nothing to undo",
        "notInUnity": "In Unity animations are removed in the editor itself — this tool only installs",
        "unityPath": "The path must be inside Assets and point to a .controller or .anim",
        "unityMissing": "No such file in the project — refresh the list",
    },
}

_state = {"project": None, "config": {}, "lang": "ru"}


class Fail(Exception):
    def __init__(self, key: str, code: int = 400):
        super().__init__(t(key))
        self.key = key
        self.code = code


def t(key: str, *args) -> str:
    text = (TEXT.get(_state["lang"]) or TEXT["ru"]).get(key) or TEXT["ru"].get(key) or key
    for i, value in enumerate(args):
        text = text.replace("{" + str(i) + "}", str(value))
    return text


# ------------------------------------------------------------ конфиг
def load_config() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_config() -> None:
    try:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(_state["config"], ensure_ascii=False, indent=2), "utf-8")
    except OSError:
        pass


def init() -> None:
    _state["config"] = load_config()


# ------------------------------------------------------------ пути
def project() -> dict | None:
    return _state["project"]


def res(file: Path | str) -> str:
    root = Path(project()["root"])
    return "res://" + str(Path(file).relative_to(root)).replace("\\", "/")


def rel(file: Path | str) -> str:
    root = Path(project()["root"])
    return str(Path(file).relative_to(root)).replace("\\", "/")


def from_res(r: str) -> Path:
    return Path(project()["root"]) / str(r or "").replace("res://", "", 1)


def inside(file: Path) -> bool:
    root = Path(project()["root"])
    try:
        relative = file.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    service = {".godot", "Library", "Temp", "Logs", "obj", "UserSettings", ".git"}
    return bool(relative.parts) and not any(p in service for p in relative.parts)


def godot_version(root: Path) -> dict:
    text = (root / "project.godot").read_text("utf-8", errors="replace")
    m = re.search(r'^config/name="((?:[^"\\]|\\.)*)"', text, re.M)
    name = json.loads('"' + (m.group(1) if m else "") + '"') if m else root.name
    f = re.search(r"^config/features=PackedStringArray\(([^)]*)\)", text, re.M)
    version = ""
    if f:
        vm = re.search(r'"(\d+\.\d+)"', f.group(1))
        version = vm.group(1) if vm else ""
    cv = re.search(r"^config_version=(\d+)", text, re.M)
    config_version = int(cv.group(1)) if cv else 0
    return {"name": name, "version": version,
            "godot4": config_version >= 5 or version.startswith("4")}


def open_project(directory: str) -> dict:
    root = Path(str(directory or "").strip().strip('"')).resolve()
    if (root / "project.godot").is_file():
        info = godot_version(root)
        if not info["godot4"]:
            raise Fail("godot3")
        _state["project"] = {"root": str(root), "name": info["name"],
                             "version": info["version"], "engine": "godot"}
    elif unity.is_unity(root):
        _state["project"] = {"root": str(root), "name": root.name,
                             "version": unity.unity_version(root), "engine": "unity"}
    else:
        raise Fail("notProject")
    cfg = _state["config"]
    recent = [str(root)] + [r for r in (cfg.get("recent") or []) if r.lower() != str(root).lower()]
    cfg["recent"] = recent[:8]
    cfg["project"] = str(root)
    save_config()
    return describe()


# ------------------------------------------------------------ персонажи Godot
def adapter():
    file = Path(project()["root"]) / ADAPTER
    if not file.is_file():
        return None
    return json.loads(file.read_text("utf-8"))


def dig(obj, key):
    return obj.get(key) if key else None


def describe_data() -> dict:
    out = {"characters": [], "errors": []}
    try:
        cfg = adapter()
    except Exception as exc:  # noqa: BLE001
        out["errors"].append(f"{ADAPTER}: {exc}")
        return out
    if not cfg:
        return out
    for n, source in enumerate(cfg.get("characters") or []):
        try:
            data = json.loads((Path(project()["root"]) / source["file"]).read_text("utf-8"))
            entries = data.get(source.get("list") or "characters") or []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                ident = str(dig(entry, source.get("id") or "id"))
                h = source.get("height") or {}
                picture = str(dig(entry, source.get("picture")) or "")
                animations = []
                for name, a in (source.get("animations") or {}).items():
                    now = entry.get(name) if isinstance(entry.get(name), dict) else None
                    animations.append({
                        "name": name, "loop": a.get("loop", True) is not False,
                        "frames": int(float(now.get("frames") or 0)) if now else 0,
                        "speed": int(float(now.get("fps") or 0)) if now else 0,
                        "installed": bool(now),
                        "hit": bool(a.get("hit_frame")) or "hit_frame" in (a.get("fields") or []),
                        "stride": "stride" in (a.get("fields") or []),
                        "fit": "sprite_scale" in (a.get("fields") or []),
                        "now": now,
                    })
                out["characters"].append({
                    "id": f"data|{n}|{ident}", "kind": "data", "name": ident,
                    "source": source["file"], "animations": animations, "fixed": True,
                    "fit": {"sprite_scale": float(dig(entry, h.get("scale")) or 1) or 1,
                            "sprite_foot": float(dig(entry, h.get("foot")) if dig(entry, h.get("foot")) is not None else 0.9),
                            "sprite_top": float(dig(entry, h.get("top")) if dig(entry, h.get("top")) is not None else 0.1)},
                    "speed": float(dig(entry, source.get("speed")) or 0) or 0,
                    "interval": float(dig(entry, source.get("interval")) or 0) or 0,
                    "folder": str(Path(picture.replace("res://", "", 1)).parent).replace(".", "")
                    if picture else "",
                })
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"{source.get('file')}: {exc}")
    return out


def scan() -> dict:
    root = Path(project()["root"])
    folders: list[str] = []
    sets: dict[str, dict] = {}
    scenes: list[Path] = []
    budget = [40000]

    def walk(directory: Path) -> None:
        if (directory / ".gdignore").is_file():
            return
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            budget[0] -= 1
            if budget[0] < 0:
                return
            if entry.is_dir():
                if entry.name.startswith(".") or entry.name == "node_modules":
                    continue
                folders.append(res(entry)[6:])
                walk(entry)
            elif entry.suffix.lower() == ".tres":
                try:
                    text = entry.read_text("utf-8", errors="replace")
                    first = text[:300].splitlines()[0] if text else ""
                    if 'type="SpriteFrames"' not in first:
                        continue
                    animations = frames.read(text)
                    if animations is not None:
                        sets[res(entry)] = {"animations": animations, "used": False}
                except OSError:
                    continue
            elif entry.suffix.lower() == ".tscn":
                scenes.append(entry)

    walk(root)
    characters = []
    for scene in scenes:
        try:
            text = scene.read_text("utf-8", errors="replace")
            sprites = frames.scene_sprites(text)
        except Exception:  # noqa: BLE001
            continue
        scene_res = res(scene)
        base = scene.stem
        for s in sprites:
            st = s.get("set") or {}
            found = sets.get(st.get("res")) if st.get("res") else None
            if found:
                found["used"] = True
            characters.append({
                "id": f"scene|{scene_res}|{s['node']}", "kind": "scene",
                "name": f"{base} / {s['node']}" if len(sprites) > 1 else base,
                "scene": scene_res, "node": s["node"], "type": s["type"],
                "holds": ("scene" if st.get("sub") else "file") if st else "none",
                "setRes": st.get("res") or None,
                "animations": (st.get("animations") if st.get("sub") else (found["animations"] if found else [])) if st else [],
                "folder": str(Path(scene_res[6:]).parent).replace(".", ""),
            })
    for r, value in sets.items():
        if value["used"]:
            continue
        characters.append({"id": f"set|{r}", "kind": "set", "name": Path(r).stem, "setRes": r,
                           "animations": value["animations"],
                           "folder": str(Path(r[6:]).parent).replace(".", "")})
    data = describe_data()
    characters.extend(data["characters"])
    characters.sort(key=lambda c: (c["kind"], c["name"].lower()))
    return {"folders": sorted(folders), "characters": characters, "adapterErrors": data["errors"]}


def describe() -> dict | None:
    p = project()
    if not p:
        return None
    base = {"root": p["root"], "name": p["name"], "version": p["version"],
            "engine": p.get("engine", "godot")}
    undo_count = sum(1 for h in (_state["config"].get("history") or []) if h.get("project") == p["root"])
    if base["engine"] == "unity":
        return {**base, "folders": unity.folders(Path(p["root"])), "characters": [],
                "adapterErrors": [], "undo": undo_count}
    return {**base, **scan(), "undo": undo_count}


# ------------------------------------------------------------ Godot
def find_godot() -> str | None:
    cfg = _state["config"]
    if cfg.get("godot") and Path(cfg["godot"]).is_file():
        return cfg["godot"]
    home = Path.home()
    places = [home / "Desktop", home / "Downloads", home / "Documents", Path("C:/Program Files"),
              Path("C:/Program Files (x86)"), Path("C:/Godot"), home / "Godot"]
    found: list[str] = []

    def look(directory: Path, depth: int) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_file() and re.match(r"^godot.*\.exe$", entry.name, re.I) and "console" not in entry.name.lower():
                found.append(str(entry))
            elif entry.is_dir() and depth > 0 and "godot" in entry.name.lower():
                look(entry, depth - 1)

    for place in places:
        if place.is_dir():
            look(place, 2)
    return sorted(found)[-1] if found else None


def import_in_godot() -> bool:
    godot = find_godot()
    if not godot:
        raise Fail("noGodot")
    profile = APP_DATA / "godot_profile"
    env = dict(os.environ)
    env["APPDATA"] = str(profile / "roaming")
    env["LOCALAPPDATA"] = str(profile / "local")
    (profile / "roaming").mkdir(parents=True, exist_ok=True)
    (profile / "local").mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run([godot, "--headless", "--path", project()["root"], "--import"],
                              env=env, timeout=300, capture_output=True,
                              creationflags=0x08000000 if os.name == "nt" else 0)
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def imported(file: Path) -> bool:
    settings = Path(str(file) + ".import")
    if not settings.is_file():
        return False
    text = settings.read_text("utf-8", errors="replace")
    m = re.search(r'^path="res://(\.godot/imported/[^"]+)"', text, re.M)
    return bool(m) and (Path(project()["root"]) / m.group(1)).is_file()


# ------------------------------------------------------------ бэкапы
def stamp() -> str:
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE)


def backup(files: list[Path], label: str) -> dict:
    root = Path(project()["root"])
    directory = APP_DATA / "backups" / _safe_name(project()["name"]) / stamp()
    entries = []
    for file in files:
        if not file:
            continue
        file = Path(file)
        relative = str(file.relative_to(root))
        existed = file.is_file()
        if existed:
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
        entries.append({"rel": relative, "existed": existed})
    record = {"project": project()["root"], "label": label, "dir": str(directory),
              "entries": entries, "time": int(time.time() * 1000)}
    cfg = _state["config"]
    cfg["history"] = [record] + (cfg.get("history") or [])
    cfg["history"] = cfg["history"][:40]
    save_config()
    return record


def undo() -> str:
    cfg = _state["config"]
    history = cfg.get("history") or []
    at = next((i for i, h in enumerate(history) if h.get("project") == project()["root"]), -1)
    if at < 0:
        raise Fail("nothingToUndo")
    record = history[at]
    root = Path(project()["root"])
    for entry in record["entries"]:
        file = root / entry["rel"]
        if entry["existed"]:
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(record["dir"]) / entry["rel"], file)
        elif file.is_file():
            file.unlink()
    history.pop(at)
    cfg["history"] = history
    save_config()
    return record["label"]


# ------------------------------------------------------------ лист
def sheet_target(directory: str, name: str) -> Path:
    safe = re.sub(r"[^\w _.\\-]+", "_", str(name or "").strip(), flags=re.UNICODE)
    safe = re.sub(r"\.png$", "", safe, flags=re.I).strip()[:80]
    if not safe:
        raise Fail("badName")
    where = str(directory or "") or ("Assets" if project() and project().get("engine") == "unity" else "")
    folder = (Path(project()["root"]) / where.replace("res://", "", 1)).resolve()
    file = folder / (safe + ".png")
    root = Path(project()["root"]).resolve()
    if not (folder == root or inside(folder)) or not inside(file):
        raise Fail("badDir")
    return file


def write_png(file: Path, png: bytes, import_template: Path | None) -> None:
    if len(png) < 8 or png[:4] != b"\x89PNG":
        raise Fail("notPng")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(png)
    settings = Path(str(file) + ".import")
    if import_template and not settings.is_file() and Path(import_template).is_file():
        lines = Path(import_template).read_text("utf-8", errors="replace").splitlines()
        kept = [ln for ln in lines if not re.match(r"^(uid|path|dest_files)=", ln)]
        kept = [f'source_file="{res(file)}"' if ln.startswith("source_file=") else ln for ln in kept]
        settings.write_text("\n".join(kept), "utf-8")


def regions(q: dict) -> list[dict]:
    n = int(float(q.get("frames") or 0))
    cols = int(float(q.get("cols") or 0)) or 1
    lead = int(float(q.get("lead") or 0))
    step_w = int(float(q.get("stepW") or 0))
    step_h = int(float(q.get("stepH") or 0))
    cell_w = int(float(q.get("cellW") or 0))
    cell_h = int(float(q.get("cellH") or 0))
    out = [{"x": (k % cols) * step_w + lead, "y": (k // cols) * step_h + lead,
            "w": cell_w, "h": cell_h} for k in range(n)]
    if not n or any(not (r["w"] > 0 and r["h"] > 0) for r in out):
        raise ValueError("bad grid")
    return out


def character(ident: str) -> dict:
    who = next((c for c in scan()["characters"] if c["id"] == ident), None)
    if not who:
        raise Fail("noCharacter")
    return who


def data_source(who: dict) -> dict:
    n = int(str(who["id"]).split("|")[1])
    cfg = adapter() or {}
    sources = cfg.get("characters") or []
    if n >= len(sources):
        raise Fail("noCharacter")
    return {"source": sources[n], "n": n}


# ------------------------------------------------------------ установка Godot
def install_data(who: dict, anim: str, q: dict, file: Path, png: bytes) -> dict:
    source = data_source(who)["source"]
    spec = (source.get("animations") or {}).get(anim)
    if not spec:
        raise Fail("noAnim")
    raw = json.loads(q.get("values") or "{}")
    raw["texture"] = res(file)
    value = {}
    for key in spec.get("fields") or []:
        if key not in DATA_VALUES:
            continue
        if key == "texture":
            value["texture"] = raw["texture"]
            continue
        try:
            v = float(raw.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"{anim}.{key}")
        value[key] = round(v) if key in ("cols", "rows", "frames", "hit_frame") else v
    value.update(spec.get("set") or {})
    data_file = Path(project()["root"]) / source["file"]
    before = data_file.read_text("utf-8", errors="replace")
    after = data_fields.set_field(before, who["name"], value, anim,
                                  {"list": source.get("list"), "id": source.get("id")})
    record = backup([file, Path(str(file) + ".import"), data_file], f"{anim} {who['name']}")
    write_png(file, png, (Path(project()["root"]) / source["import"]) if source.get("import") else None)
    if not import_in_godot() or not imported(file):
        undo()
        raise Fail("importFailed", 500)
    data_file.write_text(after, "utf-8")
    return {"ok": True, "file": res(file), "target": source["file"], "anim": anim,
            "backup": record["dir"], "imported": True}


def save_godot(q: dict, png: bytes) -> dict:
    file = sheet_target(q.get("dir"), q.get("name"))
    if file.is_file() and q.get("overwrite") != "1":
        raise Fail("exists", 409)
    backup([file, Path(str(file) + ".import")], "sheet " + res(file))
    write_png(file, png, None)
    result = {"ok": True, "file": res(file), "bytes": len(png)}
    if q.get("import") == "1":
        result["imported"] = bool(import_in_godot() and imported(file))
    return result


def install_godot(q: dict, png: bytes) -> dict:
    file = sheet_target(q.get("dir"), q.get("name"))
    if file.is_file() and q.get("overwrite") != "1":
        raise Fail("exists", 409)
    anim = str(q.get("anim") or "").strip()
    if not anim:
        raise Fail("noAnim")
    fps = max(0.1, float(q.get("fps") or 12))
    loop = q.get("loop") == "1"
    if q.get("char") == "new":
        set_path = Path(str(sheet_target(q.get("setDir"), q.get("setName")))[:-4] + ".tres")
        if set_path.is_file():
            raise Fail("exists", 409)
        record = backup([file, Path(str(file) + ".import"), set_path], f"{anim} → {res(set_path)}")
        write_png(file, png, None)
        set_path.write_text(frames.create({"name": anim, "fps": fps, "loop": loop,
                                           "texture": res(file), "regions": regions(q)}), "utf-8")
        result = {"ok": True, "file": res(file), "target": res(set_path), "created": True,
                  "anim": anim, "backup": record["dir"], "select": "set|" + res(set_path)}
        if q.get("import") == "1":
            result["imported"] = bool(import_in_godot() and imported(file))
        return result
    who = character(q.get("char"))
    if who["kind"] == "data":
        return install_data(who, anim, q, file, png)
    target = from_res(who["scene"] if who["holds"] in ("scene", "none") else who["setRes"])
    if not inside(target) or not target.is_file():
        raise Fail("badDir")
    text = target.read_text("utf-8", errors="replace")
    sub = None
    if who["kind"] == "scene" and who["holds"] != "file":
        found = next((s for s in frames.scene_sprites(text) if s["node"] == who["node"]), None) or {}
        sub = (found.get("set") or {}).get("sub")
        if not sub:
            made = frames.attach_set(text, who["node"])
            text, sub = made["text"], made["sub"]
    elif not frames.read(text):
        raise Fail("notFrames")
    nxt = frames.set_animation(text, {"name": anim, "fps": fps, "loop": loop,
                                      "texture": res(file), "regions": regions(q)}, sub)
    record = backup([file, Path(str(file) + ".import"), target], f"{anim} → {res(target)}")
    write_png(file, png, None)
    target.write_text(nxt, "utf-8")
    result = {"ok": True, "file": res(file), "target": res(target), "anim": anim,
              "backup": record["dir"]}
    if q.get("import") == "1":
        result["imported"] = bool(import_in_godot() and imported(file))
    return result


def remove_anim(q: dict) -> dict:
    if project().get("engine") == "unity":
        raise Fail("notInUnity")
    who = character(q.get("char"))
    anim = str(q.get("anim") or "")
    if who["kind"] == "data":
        source = data_source(who)["source"]
        data_file = Path(project()["root"]) / source["file"]
        before = data_file.read_text("utf-8", errors="replace")
        after = data_fields.set_field(before, who["name"], None, anim,
                                      {"list": source.get("list"), "id": source.get("id")})
        if after == before:
            return {"ok": True, "removed": False}
        backup([data_file], f"remove {anim} {who['name']}")
        data_file.write_text(after, "utf-8")
        return {"ok": True, "removed": True}
    target = from_res(who["scene"] if who["kind"] == "scene" and who["holds"] == "scene" else who["setRes"])
    if not inside(target) or not target.is_file():
        raise Fail("badDir")
    text = target.read_text("utf-8", errors="replace")
    sub = None
    if who["kind"] == "scene" and who["holds"] == "scene":
        found = next((s for s in frames.scene_sprites(text) if s["node"] == who["node"]), None) or {}
        sub = (found.get("set") or {}).get("sub")
    backup([target], f"remove {anim} ← {res(target)}")
    target.write_text(frames.remove_animation(text, anim, sub), "utf-8")
    return {"ok": True}


# ------------------------------------------------------------ Unity
def unity_asset_path(raw: str, ext: str) -> str:
    if not raw:
        return ""
    value = str(raw).replace("\\", "/").lstrip("/")
    if not value.startswith("Assets/") or not re.search(r"\.(controller|anim)$", value, re.I):
        raise Fail("unityPath")
    if not re.search(r"\." + ext + "$", value, re.I):
        raise Fail("unityPath")
    if not (Path(project()["root"]) / value).is_file():
        raise Fail("unityMissing")
    return value


def unity_events(raw: str) -> list[dict]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        frame = max(1, round(float(item.get("frame") or 1)))
        fn = str(item.get("function") or "").strip()
        if not fn:
            continue
        out.append({"frame": frame, "function": fn,
                    "stringParam": str(item.get("stringParam") or ""),
                    "intParam": round(float(item.get("intParam") or 0)),
                    "floatParam": float(item.get("floatParam") or 0)})
    return out[:64]


def unity_spec(file: Path, q: dict, size: dict) -> dict:
    return {
        "name": file.stem,
        "texW": size["width"], "texH": size["height"],
        "frames": max(1, int(float(q.get("frames") or 1))),
        "cols": max(1, int(float(q.get("cols") or 1))),
        "cellW": int(float(q.get("cellW") or 0)),
        "cellH": int(float(q.get("cellH") or 0)),
        "stepW": int(float(q.get("stepW") or 0)),
        "stepH": int(float(q.get("stepH") or 0)),
        "lead": int(float(q.get("lead") or 0)),
        "ppu": int(float(q.get("ppu") or 100)),
        "pixel": q.get("pixel") != "0",
    }


def unity_request(file: Path, q: dict, anim: str) -> Path:
    cols = max(1, int(float(q.get("cols") or 1)))
    frames_n = max(1, int(float(q.get("frames") or 1)))
    return unity.request(Path(project()["root"]), {
        "sheet": rel(file), "name": file.stem, "anim": anim,
        "fps": max(1, int(float(q.get("fps") or 12))), "loop": q.get("loop") == "1",
        "cols": cols, "rows": max(1, int(float(q.get("rows") or -(-frames_n // cols)))),
        "frames": frames_n,
        "cellW": int(float(q.get("cellW") or 0)), "cellH": int(float(q.get("cellH") or 0)),
        "stepW": int(float(q.get("stepW") or 0)), "stepH": int(float(q.get("stepH") or 0)),
        "lead": int(float(q.get("lead") or 0)), "ppu": int(float(q.get("ppu") or 100)),
        "pixel": q.get("pixel") != "0", "controller": q.get("controller") != "0",
        "controllerPath": q.get("controllerPath") or "", "clipPath": q.get("clipPath") or "",
        "events": unity_events(q.get("events") or ""),
    })


def unity_files(file: Path) -> list[Path]:
    base = str(file)[:-4]
    return [file, Path(str(file) + ".meta"), Path(base + ".anim"), Path(base + ".anim.meta"),
            Path(base + ".controller"), Path(base + ".controller.meta")]


def save_unity(q: dict, png: bytes) -> dict:
    file = sheet_target(q.get("dir"), q.get("name"))
    if file.is_file() and q.get("overwrite") != "1":
        raise Fail("exists", 409)
    size = unity.png_size(png)
    if not size:
        raise Fail("notPng")
    editor_file = unity.editor_script(Path(project()["root"]), editor_source())
    record = backup([p for p in unity_files(file) + [editor_file] if p], "sheet " + rel(file))
    file.parent.mkdir(parents=True, exist_ok=True)
    Path(str(file) + ".meta").write_text(unity.sheet_meta(unity_spec(file, q, size)), "utf-8")
    write_png(file, png, None)
    request_file = unity_request(file, q, "")
    return {"ok": True, "engine": "unity", "file": rel(file), "bytes": len(png), "pending": True,
            "request": rel(request_file), "editor": rel(editor_file), "backup": record["dir"]}


def install_unity(q: dict, png: bytes) -> dict:
    file = sheet_target(q.get("dir"), q.get("name"))
    if file.is_file() and q.get("overwrite") != "1":
        raise Fail("exists", 409)
    anim = str(q.get("anim") or "").strip()
    if not anim:
        raise Fail("noAnim")
    size = unity.png_size(png)
    if not size:
        raise Fail("notPng")
    controller_path = unity_asset_path(q.get("controllerPath") or "", "controller")
    clip_path = unity_asset_path(q.get("clipPath") or "", "anim")
    extra = [controller_path, clip_path,
             controller_path + ".meta" if controller_path else "",
             clip_path + ".meta" if clip_path else ""]
    extra_files = [Path(project()["root"]) / v for v in extra if v]
    editor_file = unity.editor_script(Path(project()["root"]), editor_source())
    record = backup([p for p in unity_files(file) + extra_files + [editor_file] if p],
                    f"{anim} → {rel(file)}")
    file.parent.mkdir(parents=True, exist_ok=True)
    Path(str(file) + ".meta").write_text(unity.sheet_meta(unity_spec(file, q, size)), "utf-8")
    write_png(file, png, None)
    request_file = unity_request(file, q, anim)
    target = clip_path or re.sub(r"\.png$", ".anim", rel(file), flags=re.I)
    return {"ok": True, "engine": "unity", "file": rel(file), "target": target,
            "controller": controller_path, "anim": anim, "pending": True,
            "request": rel(request_file), "editor": rel(editor_file), "backup": record["dir"]}


def unity_assets() -> dict:
    out = {"controllers": [], "clips": []}
    root = Path(project()["root"]) / "Assets"
    if not root.is_dir():
        return out

    def walk(directory: Path, depth: int) -> None:
        if depth > 8:
            return
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            rel_path = str(entry.relative_to(Path(project()["root"]))).replace("\\", "/")
            if entry.is_dir():
                if entry.name.startswith(".") or rel_path == "Assets/SpriteAnimStudio":
                    continue
                walk(entry, depth + 1)
            elif entry.suffix.lower() == ".controller":
                out["controllers"].append(rel_path)
            elif entry.suffix.lower() == ".anim":
                out["clips"].append(rel_path)

    walk(root, 0)
    out["controllers"].sort()
    out["clips"].sort()
    return out


def list_dir(raw: str) -> dict:
    directory = Path(str(raw or "").strip().strip('"')).resolve()
    if not directory.exists():
        raise Fail("noFolder", 404)
    if directory.is_file():
        if not IMAGES.search(directory.name):
            raise Fail("noFolder", 404)
        return {"dir": str(directory.parent), "folder": directory.stem, "files": [directory.name]}
    files = [f.name for f in directory.iterdir()
             if f.is_file() and IMAGES.search(f.name)]
    return {"dir": str(directory), "folder": directory.name, "files": files}
