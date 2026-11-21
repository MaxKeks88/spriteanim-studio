"""Сборка настольной версии SpriteAnim Studio (PyInstaller).

    python desktop/build.py

Результат — ``desktop/dist/SpriteAnimStudio/SpriteAnimStudio.exe``.
Установщик: ``desktop/SpriteAnimStudio.iss`` (Inno Setup 6) поверх этой папки.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent
ROOT = DESKTOP.parent
DIST = DESKTOP / "dist"
BUILD = DESKTOP / "build"
NAME = "SpriteAnimStudio"

DATA = [
    ("ui", "ui"),
    ("assets", "assets"),
    ("workflows", "workflows"),
    ("skills", "skills"),
    ("prompts", "prompts"),
    ("voice/py", "voice/py"),
    ("mcp", "mcp"),
    ("android-apk", "android-apk"),
    ("desktop/icon.ico", "desktop"),
]

HIDDEN = ["core", "godot_frames", "unity", "data_fields"]

COLLECT = ["webview", "pythonnet", "clr_loader"]


def run() -> int:
    for path in (DIST / NAME, BUILD):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--windowed", "--name", NAME,
        "--distpath", str(DIST), "--workpath", str(BUILD), "--specpath", str(BUILD),
        "--paths", str(ROOT), "--paths", str(ROOT / "sheet_py"),
        "--icon", str(DESKTOP / "icon.ico"),
        "--version-file", str(DESKTOP / "version_info.txt"),
    ]
    for module in COLLECT:
        args += ["--collect-all", module]
    for name in HIDDEN:
        args += ["--hidden-import", name]
    for source, target in DATA:
        src = ROOT / source
        if src.is_file():
            args += ["--add-data", f"{src};{target}"]
        elif src.is_dir():
            args += ["--add-data", f"{src};{target}"]
        else:
            print(f"!! нет папки: {src}")
    args.append(str(DESKTOP / "main.py"))
    print("PyInstaller:", " ".join(args[:6]), "…")
    return subprocess.call(args)


if __name__ == "__main__":
    raise SystemExit(run())
