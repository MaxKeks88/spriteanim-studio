"""Порт unity.js: лист PNG + .meta с нарезкой + запрос для Unity.

Имена и содержимое .meta повторяют оригинал; проверяется сравнением с JS.
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import shutil
import time
from pathlib import Path

REQUEST_DIR = "Assets/SpriteAnimStudio"
EDITOR_SCRIPT = "Assets/Editor/SpriteAnimStudio.cs"


def is_unity(root: Path) -> bool:
    return (root / "ProjectSettings" / "ProjectVersion.txt").is_file()


def unity_version(root: Path) -> str:
    text = (root / "ProjectSettings" / "ProjectVersion.txt").read_text("utf-8", errors="replace")
    m = re.search(r"m_EditorVersion:\s*(\S+)", text)
    return m.group(1) if m else ""


def folders(root: Path) -> list[str]:
    """Папки под Assets, без служебных папок Unity и нашей."""
    out = []

    def walk(directory: Path, depth: int) -> None:
        if depth > 4:
            return
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in ("Editor", "SpriteAnimStudio"):
                continue
            out.append(str(entry.relative_to(root)).replace("\\", "/"))
            walk(entry, depth + 1)

    assets = root / "Assets"
    if assets.is_dir():
        walk(assets, 1)
    return sorted(out)


def request(root: Path, spec: dict) -> Path:
    """Файл-запрос рядом с проектом: переживает перезапуск Unity."""
    directory = root / REQUEST_DIR
    directory.mkdir(parents=True, exist_ok=True)
    ident = f"{spec.get('id') or int(time.time() * 1000)}-{secrets.token_hex(3)}"
    file = directory / f"request-{ident}.json"
    file.write_text(json.dumps(spec, ensure_ascii=False, indent=1), "utf-8")
    return file


def editor_script(root: Path, source: Path) -> Path | None:
    target = root / EDITOR_SCRIPT
    if not source.is_file():
        return None
    text = source.read_text("utf-8")
    if target.is_file() and target.read_text("utf-8") == text:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, "utf-8")
    return target


def new_guid() -> str:
    return secrets.token_hex(16)


def new_internal_id() -> str:
    data = bytearray(secrets.token_bytes(8))
    data[0] &= 0x3F                       # как в JS: оставляем положительным
    return str(int.from_bytes(bytes(data), "big"))


def png_size(buffer: bytes) -> dict | None:
    if not buffer or len(buffer) < 24 or int.from_bytes(buffer[:4], "big") != 0x89504E47:
        return None
    return {"width": int.from_bytes(buffer[16:20], "big"),
            "height": int.from_bytes(buffer[20:24], "big")}


def sheet_meta(spec: dict) -> str:
    frames = max(1, int(spec.get("frames") or 1))
    cols = max(1, int(spec.get("cols") or 1))
    tex_w = int(spec.get("texW") or 0)
    tex_h = int(spec.get("texH") or 0)
    cell_w = max(1, int(spec.get("cellW") or (tex_w // cols if tex_w else 0) or 1))
    rows = max(1, math.ceil(frames / cols))
    cell_h = max(1, int(spec.get("cellH") or (tex_h // rows if tex_h else 0) or 1))
    step_w = int(spec.get("stepW") or 0) if int(spec.get("stepW") or 0) > 0 else cell_w
    step_h = int(spec.get("stepH") or 0) if int(spec.get("stepH") or 0) > 0 else cell_h
    lead = int(spec.get("lead") or 0)
    pixel = spec.get("pixel", True) is not False
    ppu = int(spec.get("ppu") or 100)
    max_size = min(8192, max(2048, 2 ** math.ceil(math.log2(max(tex_w, tex_h, 1)))))
    guid = new_guid()
    sprites = []
    id_table = []
    name_table = []
    name = str(spec.get("name") or "")
    for i in range(frames):
        column = i % cols
        row = i // cols
        x = column * step_w + lead
        y = tex_h - (row * step_h + lead) - cell_h   # Unity считает строки снизу
        sprite_name = f"{name}_{i + 1}"
        internal_id = new_internal_id()
        sprite_id = new_guid()
        name_table.append(f"      {sprite_name}: {internal_id}")
        id_table.append(f"  - first:\n      213: {internal_id}\n    second: {sprite_name}")
        sprites.append("\n".join([
            "    - serializedVersion: 2",
            f"      name: {sprite_name}",
            "      rect:",
            "        serializedVersion: 2",
            f"        x: {x}",
            f"        y: {y}",
            f"        width: {cell_w}",
            f"        height: {cell_h}",
            "      alignment: 0",
            "      pivot: {x: 0, y: 0}",
            "      border: {x: 0, y: 0, z: 0, w: 0}",
            "      customData: ",
            "      outline: []",
            "      physicsShape: []",
            "      tessellationDetail: -1",
            "      bones: []",
            f"      spriteID: {sprite_id}",
            f"      internalID: {internal_id}",
            "      vertices: []",
            "      indices: ",
            "      edges: []",
            "      weights: []",
        ]))

    def platform(target: str) -> str:
        return "\n".join([
            "  - serializedVersion: 4",
            f"    buildTarget: {target}",
            f"    maxTextureSize: {max_size}",
            "    resizeAlgorithm: 0",
            "    textureFormat: -1",
            "    textureCompression: " + ("0" if pixel else "1"),
            "    compressionQuality: 50",
            "    crunchedCompression: 0",
            "    allowsAlphaSplitting: 0",
            "    overridden: 0",
            "    ignorePlatformSupport: 0",
            "    androidETC2FallbackOverride: 0",
            "    forceMaximumCompressionQuality_BC6H_BC7: 0",
        ])

    return "\n".join([
        "fileFormatVersion: 2",
        f"guid: {guid}",
        "TextureImporter:",
        "  internalIDToNameTable:",
        "\n".join(id_table),
        "  externalObjects: {}",
        "  serializedVersion: 13",
        "  mipmaps:",
        "    mipMapMode: 0",
        "    enableMipMap: 0",
        "    sRGBTexture: 1",
        "    linearTexture: 0",
        "    fadeOut: 0",
        "    borderMipMap: 0",
        "    mipMapsPreserveCoverage: 0",
        "    alphaTestReferenceValue: 0.5",
        "    mipMapFadeDistanceStart: 1",
        "    mipMapFadeDistanceEnd: 3",
        "  bumpmap:",
        "    convertToNormalMap: 0",
        "    externalNormalMap: 0",
        "    heightScale: 0.25",
        "    normalMapFilter: 0",
        "    flipGreenChannel: 0",
        "  isReadable: 0",
        "  streamingMipmaps: 0",
        "  streamingMipmapsPriority: 0",
        "  vTOnly: 0",
        "  ignoreMipmapLimit: 0",
        "  grayScaleToAlpha: 0",
        "  generateCubemap: 6",
        "  cubemapConvolution: 0",
        "  seamlessCubemap: 0",
        "  textureFormat: 1",
        f"  maxTextureSize: {max_size}",
        "  textureSettings:",
        "    serializedVersion: 2",
        "    filterMode: " + ("0" if pixel else "1"),
        "    aniso: 1",
        "    mipBias: 0",
        "    wrapU: 1",
        "    wrapV: 1",
        "    wrapW: 1",
        "  nPOTScale: 0",
        "  lightmap: 0",
        "  compressionQuality: 50",
        "  spriteMode: 2",
        "  spriteExtrude: 1",
        "  spriteMeshType: 1",
        "  alignment: 0",
        "  spritePivot: {x: 0.5, y: 0.5}",
        f"  spritePixelsToUnits: {ppu}",
        "  spriteBorder: {x: 0, y: 0, z: 0, w: 0}",
        "  spriteGenerateFallbackPhysicsShape: 1",
        "  alphaUsage: 1",
        "  alphaIsTransparency: 1",
        "  spriteTessellationMethod: 0",
        "  spriteTessellationDetail: -1",
        "  spriteGeometrySubdivision: -1",
        "  textureType: 8",
        "  textureShape: 1",
        "  singleChannelComponent: 0",
        "  flipbookRows: 1",
        "  flipbookColumns: 1",
        "  maxTextureSizeSet: 0",
        "  compressionQualitySet: 0",
        "  textureFormatSet: 0",
        "  ignorePngGamma: 0",
        "  applyGammaDecoding: 0",
        "  swizzle: 50462976",
        "  cookieLightType: 0",
        "  platformSettings:",
        platform("DefaultTexturePlatform"),
        platform("Standalone"),
        platform("WebGL"),
        "  spriteSheet:",
        "    serializedVersion: 2",
        "    sprites:",
        "\n".join(sprites),
        "    outline: []",
        "    customData: ",
        "    physicsShape: []",
        "    bones: []",
        "    spriteID: ",
        "    internalID: 0",
        "    vertices: []",
        "    indices: ",
        "    edges: []",
        "    weights: []",
        "    secondaryTextures: []",
        "    spriteCustomMetadata:",
        "      entries: []",
        "    nameFileIdTable:",
        "\n".join(name_table),
        "  mipmapLimitGroupName: ",
        "  pSDRemoveMatte: 0",
        "  userData: ",
        "  assetBundleName: ",
        "  assetBundleVariant: ",
        "",
    ])
