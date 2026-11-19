"""Порт godot_frames.js: SpriteFrames в .tres и внутри .tscn.

Правит файл секциями: не тронутые секции сохраняют свой текст, поэтому Godot
видит ту же сцену/ресурс с изменённой анимацией. Совместим по выводу с
оригиналом (проверяется сравнением строк).
"""

from __future__ import annotations

import json
import math
import random
import re

SECTION = re.compile(r"^\[(gd_resource|gd_scene|ext_resource|sub_resource|resource|node|connection|editable)(\s[^\n]*)?\]\s*$")
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


class Value:
    """Значение Godot: raw / arr / dict / ctor."""

    __slots__ = ("t", "raw", "items", "entries", "name", "args")

    def __init__(self, t, raw=None, items=None, entries=None, name=None, args=None):
        self.t = t
        self.raw = raw
        self.items = items
        self.entries = entries
        self.name = name
        self.args = args

    def __repr__(self):  # для отладки
        return show(self)


def raw(r: str) -> Value:
    return Value("raw", raw=r)


def split(text: str) -> dict:
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = re.split(r"\r?\n", text)
    sections = []
    current = {"head": None, "kind": None, "lines": []}
    for line in lines:
        m = SECTION.match(line)
        if m:
            sections.append(current)
            current = {"head": line, "kind": m.group(1), "lines": []}
        else:
            current["lines"].append(line)
    sections.append(current)
    return {"eol": eol, "sections": sections}


def join(file: dict) -> str:
    out = []
    for s in file["sections"]:
        if s["head"] is not None:
            out.append(s["head"])
        out.extend(s["lines"])
    return file["eol"].join(out)


def attrs(head: str | None) -> dict:
    out = {}
    if not head:
        return out
    for m in re.finditer(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s\]]+)', head, re.ASCII):
        value = m.group(2)
        out[m.group(1)] = json.loads(value) if value.startswith('"') else value
    return out


def parse_value(s: str, i: int = 0) -> tuple[Value, int]:
    n = len(s)

    def ws():
        nonlocal i
        while i < n and s[i].isspace():
            i += 1

    def parse_string():
        nonlocal i
        start = i
        i += 1
        while i < n and s[i] != '"':
            if s[i] == "\\":
                i += 1
            i += 1
        i += 1
        return s[start:i]

    def value():
        nonlocal i
        ws()
        c = s[i] if i < n else ""
        if c == "[":
            i += 1
            items = []
            ws()
            if i < n and s[i] == "]":
                i += 1
                return Value("arr", items=items)
            while True:
                items.append(value())
                ws()
                if i < n and s[i] == ",":
                    i += 1
                    continue
                if i < n and s[i] == "]":
                    i += 1
                    return Value("arr", items=items)
                raise ValueError(f"array at {i}")
        if c == "{":
            i += 1
            entries = []
            ws()
            if i < n and s[i] == "}":
                i += 1
                return Value("dict", entries=entries)
            while True:
                ws()
                key = value()
                ws()
                if i >= n or s[i] != ":":
                    raise ValueError(f"dictionary at {i}")
                i += 1
                entries.append((key, value()))
                ws()
                if i < n and s[i] == ",":
                    i += 1
                    continue
                if i < n and s[i] == "}":
                    i += 1
                    return Value("dict", entries=entries)
                raise ValueError(f"dictionary at {i}")
        if c == '"':
            return Value("raw", raw=parse_string())
        if c in "&^" and i + 1 < n and s[i + 1] == '"':
            i += 1
            return Value("raw", raw=c + parse_string())
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[i:])
        if m:
            i += len(m.group(0))
            ws()
            if i >= n or s[i] != "(":
                return Value("raw", raw=m.group(0))
            i += 1
            args = []
            ws()
            if i < n and s[i] == ")":
                i += 1
                return Value("ctor", name=m.group(0), args=args)
            while True:
                args.append(value())
                ws()
                if i < n and s[i] == ",":
                    i += 1
                    continue
                if i < n and s[i] == ")":
                    i += 1
                    return Value("ctor", name=m.group(0), args=args)
                raise ValueError(f"constructor at {i}")
        m = re.match(r"-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?", s[i:], re.I)
        if m:
            i += len(m.group(0))
            return Value("raw", raw=m.group(0))
        raise ValueError(f"unexpected «{s[i:i + 12]}»")

    v = value()
    return v, i


def show(v: Value) -> str:
    if v.t == "raw":
        return v.raw
    if v.t == "arr":
        return "[" + ", ".join(show(x) for x in v.items) + "]"
    if v.t == "ctor":
        return v.name + "(" + ", ".join(show(x) for x in v.args) + ")"
    if not v.entries:
        return "{}"
    return "{\n" + ",\n".join(show(k) + ": " + show(x) for k, x in v.entries) + "\n}"


def quote(text: str) -> str:
    return json.dumps(str(text), ensure_ascii=False)


def unquote(r: str) -> str:
    return json.loads(r[1:] if r[:1] in "&^" else r)


def float_str(n: float) -> str:
    v = math.floor(n * 1000 + 0.5) / 1000
    r = str(int(v)) if v == int(v) else str(v)
    return r + ".0" if not re.search(r"[.eE]", r) else r


def field(d: Value, key: str) -> Value | None:
    want = quote(key)
    for k, v in d.entries:
        if k.t == "raw" and k.raw == want:
            return v
    return None


def holder_of(file: dict, sub_id: str | None):
    if not sub_id:
        return next((s for s in file["sections"] if s["kind"] == "resource"), None)
    for s in file["sections"]:
        if s["kind"] == "sub_resource":
            a = attrs(s["head"])
            if a.get("id") == sub_id and a.get("type") == "SpriteFrames":
                return s
    return None


def animations_of(file: dict, sub_id: str | None):
    res = holder_of(file, sub_id)
    if not res:
        return {"res": None, "list": None, "span": None}
    body = "\n".join(res["lines"])
    m = re.search(r"^animations\s*=\s*", body, re.M)
    if not m:
        return {"res": res, "list": Value("arr", items=[]), "span": None}
    start = m.end()
    parsed, end = parse_value(body, start)
    return {"res": res, "list": parsed, "span": (m.start(), end)}


def write_animations(file: dict, found: dict) -> None:
    text = "animations = " + show(found["list"])
    res = found["res"]
    body = "\n".join(res["lines"])
    if found["span"]:
        a, b = found["span"]
        nxt = body[:a] + text + body[b:]
    else:
        nxt = text + ("\n" + body if body.strip() else body)
    res["lines"] = nxt.split("\n")


def describe(list_: Value | None) -> list[dict]:
    out = []
    for a in (list_.items if list_ else []):
        frames = field(a, "frames")
        name = field(a, "name")
        speed = field(a, "speed")
        loop = field(a, "loop")
        sp = 5
        if speed:
            sp = float(speed.raw)
            if sp.is_integer():
                sp = int(sp)
        out.append({
            "name": unquote(name.raw) if name else "",
            "frames": len(frames.items) if frames and frames.t == "arr" else 0,
            "speed": sp,
            "loop": (loop.raw not in ("false", "0")) if loop else True,
        })
    return out


def is_set(file: dict) -> bool:
    head = next((s for s in file["sections"] if s["kind"] == "gd_resource"), None)
    return bool(head) and attrs(head["head"]).get("type") == "SpriteFrames"


def read(text: str, sub_id: str | None = None):
    file = split(text)
    if not sub_id and not is_set(file):
        return None
    if sub_id and not holder_of(file, sub_id):
        return None
    return describe(animations_of(file, sub_id)["list"])


def node_path_of(a: dict) -> str:
    parent = a.get("parent")
    return a.get("name", "") if parent in (None, ".") else f"{parent}/{a.get('name', '')}"


def scene_sprites(text: str) -> list[dict]:
    file = split(text)
    ext = {}
    for s in file["sections"]:
        if s["kind"] == "ext_resource":
            a = attrs(s["head"])
            ext[a.get("id")] = a
    out = []
    for s in file["sections"]:
        if s["kind"] != "node":
            continue
        a = attrs(s["head"])
        if not re.match(r"^AnimatedSprite(2D|3D)$", a.get("type") or ""):
            continue
        body = "\n".join(s["lines"])
        m = re.search(r'^sprite_frames\s*=\s*(SubResource|ExtResource)\(\s*"([^"]+)"\s*\)', body, re.M)
        st = None
        if m and m.group(1) == "SubResource":
            st = {"sub": m.group(2), "animations": read(text, m.group(2)) or []}
        elif m and m.group(2) in ext:
            st = {"res": ext[m.group(2)].get("path")}
        out.append({"node": node_path_of(a), "type": a.get("type"),
                    "root": "parent" not in a, "set": st})
    return out


def _suffix() -> str:
    return "".join(random.choice(ALPHABET) for _ in range(5))


def ids(file: dict, kind: str) -> list[str]:
    return [attrs(s["head"]).get("id") for s in file["sections"] if s["kind"] == kind]


def references(file: dict) -> dict:
    sub, ex = {}, {}
    for s in file["sections"]:
        own = attrs(s["head"]).get("id") if s["kind"] == "sub_resource" else None
        text = "\n".join(s["lines"]) + (" " + (s["head"] or "") if s["kind"] == "node" else "")
        for m in re.finditer(r'SubResource\(\s*"([^"]+)"\s*\)', text):
            if m.group(1) != own:
                sub[m.group(1)] = sub.get(m.group(1), 0) + 1
        for m in re.finditer(r'ExtResource\(\s*"([^"]+)"\s*\)', text):
            ex[m.group(1)] = ex.get(m.group(1), 0) + 1
    return {"sub": sub, "ext": ex}


def prune(file: dict, before: dict) -> None:
    for _ in range(4):
        now = references(file)
        dropped = False
        kept = []
        for s in file["sections"]:
            if s["kind"] not in ("sub_resource", "ext_resource"):
                kept.append(s)
                continue
            ident = attrs(s["head"]).get("id")
            key = "sub" if s["kind"] == "sub_resource" else "ext"
            if before[key].get(ident, 0) > 0 and not now[key].get(ident, 0):
                dropped = True
                continue
            kept.append(s)
        file["sections"] = kept
        if not dropped:
            break


def fix_load_steps(file: dict) -> None:
    head = next((s for s in file["sections"] if s["kind"] in ("gd_resource", "gd_scene")), None)
    if not head or not re.search(r"load_steps=\d+", head["head"]):
        return
    steps = sum(1 for s in file["sections"] if s["kind"] in ("ext_resource", "sub_resource")) + 1
    head["head"] = re.sub(r"load_steps=\d+", f"load_steps={steps}", head["head"])


def insert(file: dict, section: dict, after: list[str], before: dict | None = None) -> None:
    if not section["lines"] or section["lines"][-1] != "":
        section["lines"].append("")
    sections = file["sections"]
    if before is not None:
        at = sections.index(before)
        prev = sections[at - 1] if at > 0 else None
        if prev and (not prev["lines"] or prev["lines"][-1] != ""):
            prev["lines"].append("")
        sections.insert(at, section)
        return
    at = -1
    for k, s in enumerate(sections):
        if s["kind"] in after:
            at = k
    if at < 0:
        at = 0
    prev = sections[at]
    if not prev["lines"] or prev["lines"][-1] != "":
        prev["lines"].append("")
    sections.insert(at + 1, section)


def set_animation(text: str, anim: dict, sub_id: str | None = None) -> str:
    """anim: {name, fps, loop, texture, regions: [{x,y,w,h}]}."""
    file = split(text)
    if not sub_id and not is_set(file):
        raise ValueError("not a SpriteFrames resource")
    if sub_id and not holder_of(file, sub_id):
        raise ValueError(f"no SpriteFrames {sub_id} in the scene")
    before = references(file)
    ext = next((s for s in file["sections"]
                if s["kind"] == "ext_resource" and attrs(s["head"]).get("path") == anim["texture"]), None)
    if ext:
        ext_id = attrs(ext["head"])["id"]
    else:
        taken = set(ids(file, "ext_resource"))
        nums = [int(x) for x in taken if str(x).isdigit()]
        first = (max(nums) if nums else 0) + 1
        while True:
            ext_id = f"{first}_{_suffix()}"
            if ext_id not in taken:
                break
        insert(file, {"head": f'[ext_resource type="Texture2D" path={quote(anim["texture"])} id={quote(ext_id)}]',
                      "kind": "ext_resource", "lines": []},
               ["gd_resource", "gd_scene", "ext_resource"])
    if not sub_id and not holder_of(file, None):
        insert(file, {"head": "[resource]", "kind": "resource", "lines": []},
               ["gd_resource", "ext_resource", "sub_resource"])
    holder = holder_of(file, sub_id)
    taken_sub = set(ids(file, "sub_resource"))
    frames = []
    for r in anim["regions"]:
        while True:
            ident = "AtlasTexture_" + _suffix()
            if ident not in taken_sub:
                break
        taken_sub.add(ident)
        section = {"head": f'[sub_resource type="AtlasTexture" id={quote(ident)}]', "kind": "sub_resource",
                   "lines": [f"atlas = ExtResource({quote(ext_id)})",
                             "region = Rect2(" + ", ".join(str(x) for x in (r["x"], r["y"], r["w"], r["h"])) + ")",
                             "filter_clip = true"]}
        insert(file, section, [], holder)
        frames.append(Value("dict", entries=[
            (raw('"duration"'), raw("1.0")),
            (raw('"texture"'), Value("ctor", name="SubResource", args=[raw(quote(ident))])),
        ]))
    found = animations_of(file, sub_id)
    entry = Value("dict", entries=[
        (raw('"frames"'), Value("arr", items=frames)),
        (raw('"loop"'), raw("true" if anim.get("loop") else "false")),
        (raw('"name"'), raw("&" + quote(anim["name"]))),
        (raw('"speed"'), raw(float_str(float(anim.get("fps") or 5)))),
    ])
    at = -1
    for i, a in enumerate(found["list"].items):
        n = field(a, "name")
        if n and unquote(n.raw) == anim["name"]:
            at = i
            break
    if at >= 0:
        found["list"].items[at] = entry
    else:
        found["list"].items.append(entry)
    write_animations(file, found)
    prune(file, before)
    fix_load_steps(file)
    return join(file)


def remove_animation(text: str, name: str, sub_id: str | None = None) -> str:
    file = split(text)
    before = references(file)
    found = animations_of(file, sub_id)
    if not found["list"]:
        return text
    left = []
    for a in found["list"].items:
        n = field(a, "name")
        if n and unquote(n.raw) == name:
            continue
        left.append(a)
    if len(left) == len(found["list"].items):
        return text
    found["list"].items = left
    write_animations(file, found)
    prune(file, before)
    fix_load_steps(file)
    return join(file)


def create(anim: dict) -> str:
    base = '[gd_resource type="SpriteFrames" load_steps=1 format=3]\n\n[resource]\nanimations = []\n'
    return set_animation(base, anim)


def attach_set(text: str, node_path: str) -> dict:
    file = split(text)
    node = next((s for s in file["sections"] if s["kind"] == "node"
                 and node_path_of(attrs(s["head"])) == node_path), None)
    if node is None:
        raise ValueError(f"no node {node_path} in the scene")
    taken = set(ids(file, "sub_resource"))
    while True:
        ident = "SpriteFrames_" + _suffix()
        if ident not in taken:
            break
    first_node = next((s for s in file["sections"] if s["kind"] == "node"), None)
    insert(file, {"head": f'[sub_resource type="SpriteFrames" id={quote(ident)}]',
                  "kind": "sub_resource", "lines": ["animations = []"]}, [], first_node)
    line = f"sprite_frames = SubResource({quote(ident)})"
    at = next((i for i, l in enumerate(node["lines"]) if re.match(r"^sprite_frames\s*=", l)), -1)
    if at >= 0:
        node["lines"][at] = line
    else:
        node["lines"].insert(0, line)
    fix_load_steps(file)
    return {"text": join(file), "sub": ident}
