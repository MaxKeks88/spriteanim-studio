"""Сборка SpriteAnim Studio через PyInstaller (папка dist/SpriteAnimStudio).

    python build/build.py

Результат — папка с .exe и ресурсами; .cache/, output/, voice/ создаются рядом
с .exe при первом запуске. Для сборки нужен установленный pyinstaller.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "work"
NAME = "SpriteAnimStudio"

DATA = [
    ("ui", "ui"),
    ("assets", "assets"),
    ("workflows", "workflows"),
    ("skills", "skills"),
    ("prompts", "prompts"),
    ("voice/py", "voice/py"),
    ("mcp", "mcp"),
]

HIDDEN = ["core", "godot_frames", "unity", "data_fields"]


def run() -> int:
    for path in (DIST / NAME, BUILD):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--windowed", "--name", NAME, "--distpath", str(DIST),
            "--workpath", str(BUILD), "--specpath", str(BUILD),
            "--paths", str(ROOT / "sheet_py")]
    for name in HIDDEN:
        args += ["--hidden-import", name]
    for source, target in DATA:
        src = ROOT / source
        if src.exists():
            args += ["--add-data", f"{src}{';' if sys.platform == 'win32' else ':'}{target}"]
    args.append(str(ROOT / "app.py"))
    print("PyInstaller:", " ".join(args[:8]), "...")
    return subprocess.call(args)


if __name__ == "__main__":
    raise SystemExit(run())
