"""Порт data_fields.js: правка одного поля записи в JSON игры по тексту.

Порядок полей, отступы и переводы строк сохраняются; после правки текст
разбирается заново и сверяется с задуманным — иначе ничего не пишется.
"""

from __future__ import annotations

import json


def value_end(text: str, i: int) -> int:
    c = text[i] if i < len(text) else ""
    if c == '"':
        j = i + 1
        while j < len(text):
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == '"':
                return j + 1
            j += 1
        raise ValueError("строка не закрыта")
    if c in "{[":
        depth = 0
        j = i
        while j < len(text):
            d = text[j]
            if d == '"':
                j = value_end(text, j)
                continue
            if d in "{[":
                depth += 1
            elif d in "}]":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise ValueError("скобка не закрыта")
    j = i
    while j < len(text) and text[j] not in " \t\r\n,}]":
        j += 1
    return j


def skip(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def members(text: str, open_at: int) -> list[dict]:
    out = []
    i = skip(text, open_at + 1)
    while i < len(text) and text[i] != "}":
        key_start = i
        key_end = value_end(text, i)
        key = json.loads(text[key_start:key_end])
        i = skip(text, key_end)
        if i >= len(text) or text[i] != ":":
            raise ValueError(f"нет двоеточия после {key}")
        value_start = skip(text, i + 1)
        end = value_end(text, value_start)
        out.append({"key": key, "keyStart": key_start, "valueStart": value_start, "valueEnd": end})
        i = skip(text, end)
        if i < len(text) and text[i] == ",":
            i = skip(text, i + 1)
    return out


def elements(text: str, open_at: int) -> list[int]:
    out = []
    i = skip(text, open_at + 1)
    while i < len(text) and text[i] != "]":
        out.append(i)
        i = skip(text, value_end(text, i))
        if i < len(text) and text[i] == ",":
            i = skip(text, i + 1)
    return out


def line_indent(text: str, i: int) -> str:
    start = text.rfind("\n", 0, i) + 1
    line = text[start:i]
    return line[: len(line) - len(line.lstrip(" \t"))]


def find_entry(text: str, ident, where: dict) -> dict:
    list_key = where.get("list") or "characters"
    id_key = where.get("id") or "id"
    root = skip(text, 0)
    lst = next((m for m in members(text, root) if m["key"] == list_key), None)
    if not lst or text[lst["valueStart"]] != "[":
        raise ValueError(f'no array «{list_key}» in the file')
    for start in elements(text, lst["valueStart"]):
        if text[start] != "{":
            continue
        fields = members(text, start)
        id_field = next((m for m in fields if m["key"] == id_key), None)
        if id_field and str(json.loads(text[id_field["valueStart"]:id_field["valueEnd"]])) == str(ident):
            return {"start": start, "fields": fields}
    raise ValueError(f'no entry «{ident}» in «{list_key}»')


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def render(key: str, value: dict, indent: str, unit: str, eol: str) -> str:
    inner = [indent + unit + _js(k) + ": " + _js(v) for k, v in value.items()]
    return _js(key) + ": {" + eol + ("," + eol).join(inner) + eol + indent + "}"


def check(text: str, ident, value, key: str, where: dict) -> None:
    data = json.loads(text)
    lst = data.get(where.get("list") or "characters") or []
    entry = next((e for e in lst
                  if e and str(e.get(where.get("id") or "id")) == str(ident)), None)
    if entry is None:
        raise ValueError("the entry is gone after the change")
    current = entry.get(key, None)
    if _js(current) != _js(value):
        raise ValueError(key + " did not come out as meant")


def set_field(text: str, ident, value, key: str, where: dict | None = None) -> str:
    where = where or {}
    eol = "\r\n" if "\r\n" in text else "\n"
    found = find_entry(text, ident, where)
    fields, start = found["fields"], found["start"]
    if not fields:
        raise ValueError("the entry has no fields")
    indent = line_indent(text, fields[0]["keyStart"])
    outer = line_indent(text, start)
    unit = indent[len(outer):] if len(indent) > len(outer) else "  "
    old = next((m for m in fields if m["key"] == key), None)
    if value is None:
        if not old:
            return text
        at = fields.index(old)
        if at > 0:
            out = text[: fields[at - 1]["valueEnd"]] + text[old["valueEnd"]:]
        else:
            nxt = fields[1] if len(fields) > 1 else None
            out = text[: old["keyStart"]] + (text[nxt["keyStart"]:] if nxt else text[skip(text, old["valueEnd"]):])
    elif old:
        out = text[: old["keyStart"]] + render(key, value, indent, unit, eol) + text[old["valueEnd"]:]
    else:
        last = fields[-1]
        out = (text[: last["valueEnd"]] + "," + eol + indent
               + render(key, value, indent, unit, eol) + text[last["valueEnd"]:])
    check(out, ident, value, key, where)
    return out
