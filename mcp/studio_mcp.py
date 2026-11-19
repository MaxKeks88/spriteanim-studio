"""MCP-сервер SpriteAnim Studio (stdio, без зависимостей).

Подключается к запущенному приложению (http://127.0.0.1:8189) и даёт агенту
(Claude Code, Codex и любой другой MCP-клиент) инструменты: сгенерировать
картинку, анимацию, убрать фон, написать промпт агентом, следить за заданием.

Запуск (клиент запускает сам):
    python E:\\SpriteAnim Studio\\mcp\\studio_mcp.py
"""

from __future__ import annotations

import base64
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8189"
DEFAULT_TIMEOUT = 900


def api(path: str, body=None, timeout: float = 60, raw: bool = False):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode("utf-8", "replace")
    return text if raw else json.loads(text)


def data_url(path: str) -> str:
    file = Path(path).expanduser()
    if not file.is_file():
        raise ValueError(f"нет файла: {path}")
    ctype = mimetypes.guess_type(file.name)[0] or "image/png"
    return f"data:{ctype};base64," + base64.b64encode(file.read_bytes()).decode("ascii")


def image_size(base: int, aspect: str) -> tuple[int, int]:
    try:
        a, b = (int(x) for x in aspect.split(":"))
    except Exception:  # noqa: BLE001
        a = b = 1
    base = max(256, min(2048, int(base or 1024)))
    if a >= b:
        return base, max(256, round(base * b / a / 16) * 16)
    return max(256, round(base * a / b / 16) * 16), base


TOOLS = [
    {
        "name": "studio_status",
        "description": "Состояние SpriteAnim Studio: ComfyUI, модели, активные задания.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_image",
        "description": "Сгенерировать изображение (Qwen Image 2.1) и вернуть id задания.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Описание картинки"},
                "size": {"type": "integer", "description": "768, 1024 или 1536", "default": 1024},
                "aspect": {"type": "string", "description": "1:1, 16:9, 9:16, 4:3, 3:4", "default": "1:1"},
                "steps": {"type": "integer", "default": 25},
                "seed": {"type": "integer", "default": 0},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "generate_animation",
        "description": "Сгенерировать спрайтовую анимацию по картинке персонажа (MiniMax H3). Возвращает id задания.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Что делает персонаж"},
                "image_path": {"type": "string", "description": "Путь к PNG/JPG персонажа"},
                "mode": {"type": "string", "description": "cycle (петля) или once (один раз)", "default": "cycle"},
                "length": {"type": "integer", "description": "кадров", "default": 124},
                "width": {"type": "integer", "default": 512},
                "height": {"type": "integer", "default": 512},
                "steps": {"type": "integer", "default": 20},
                "seed": {"type": "integer", "default": 0},
                "name": {"type": "string", "description": "имя клипа", "default": ""},
            },
            "required": ["prompt", "image_path"],
        },
    },
    {
        "name": "remove_background",
        "description": "Убрать фон с картинки и получить PNG с альфой. Возвращает id задания.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "resolution": {"type": "integer", "default": 1024},
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "agent_prompt",
        "description": "Попросить локального агента (Gemma) написать промпт по короткой идее.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brief": {"type": "string"},
                "skill": {"type": "string", "description": "например sprite-animation или flux2-klein"},
                "mode": {"type": "string", "description": "image или gen", "default": "image"},
                "image_path": {"type": "string", "description": "необязательный исходник"},
            },
            "required": ["brief"],
        },
    },
    {
        "name": "job_status",
        "description": "Статус задания по id: state (queued/running/done/error), outputs, error.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "wait_job",
        "description": "Дождаться завершения задания (по умолчанию до 10 минут) и вернуть результат.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "timeout_sec": {"type": "integer", "default": 600},
                "interval_sec": {"type": "integer", "default": 3},
            },
            "required": ["id"],
        },
    },
    {
        "name": "list_runs",
        "description": "Последние прогоны из истории (параметры и пути к файлам).",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
    },
]


def call_tool(name: str, args: dict) -> dict:
    if name == "studio_status":
        state = api("/api/state")
        jobs = api("/api/jobs").get("jobs", [])
        return {
            "comfy": state.get("comfy"),
            "image_models": state.get("image", {}).get("models", []),
            "agent": state.get("agent"),
            "jobs": jobs,
        }

    if name == "generate_image":
        prompt = str(args.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("нужен prompt")
        base = int(args.get("size") or 1024)
        aspect = str(args.get("aspect") or "1:1")
        w, h = image_size(base, aspect)
        return api("/api/image/generate", {
            "model": "qwen21", "prompt": prompt, "aspect": aspect, "base": base,
            "width": w, "height": h, "steps": int(args.get("steps") or 25),
            "seed": int(args.get("seed") or 0), "refs": [], "ref_mode": "off",
        }, timeout=120)

    if name == "generate_animation":
        prompt = str(args.get("prompt") or "").strip()
        path = str(args.get("image_path") or "").strip()
        if not prompt or not path:
            raise ValueError("нужны prompt и image_path")
        return api("/api/generate", {
            "mode": str(args.get("mode") or "cycle"),
            "name": str(args.get("name") or ""),
            "prompt": prompt,
            "image": {"name": Path(path).name, "data": data_url(path)},
            "width": int(args.get("width") or 512),
            "height": int(args.get("height") or 512),
            "length": int(args.get("length") or 124),
            "seed": int(args.get("seed") or 0),
            "steps": int(args.get("steps") or 20),
            "advanced": {"key_color": "magenta", "clip_black": 0.04, "clip_white": 0.97,
                         "choke_px": 0, "edge_bleed_px": 4, "max_frames": 0,
                         "dedupe_twos": True},
        }, timeout=120)

    if name == "remove_background":
        path = str(args.get("image_path") or "").strip()
        if not path:
            raise ValueError("нужен image_path")
        return api("/api/bg", {
            "image": data_url(path),
            "prompt": "Remove the background, and output a PNG image",
            "resolution": int(args.get("resolution") or 1024),
        }, timeout=120)

    if name == "agent_prompt":
        brief = str(args.get("brief") or "").strip()
        if not brief:
            raise ValueError("нужен brief")
        payload = {"brief": brief, "mode": str(args.get("mode") or "image")}
        if args.get("skill"):
            payload["skill"] = str(args["skill"])
        if args.get("image_path"):
            payload["image"] = data_url(str(args["image_path"]))
        return api("/api/agent/prompt", payload, timeout=DEFAULT_TIMEOUT)

    if name == "job_status":
        return api("/api/job?id=" + urllib.parse.quote(str(args.get("id") or "")))

    if name == "wait_job":
        job_id = str(args.get("id") or "")
        deadline = time.time() + int(args.get("timeout_sec") or 600)
        interval = max(1, int(args.get("interval_sec") or 3))
        while True:
            status = api("/api/job?id=" + urllib.parse.quote(job_id))
            if status.get("state") in ("done", "error", "unknown") or time.time() >= deadline:
                return status
            time.sleep(interval)

    if name == "list_runs":
        return api("/api/runs?limit=" + str(int(args.get("limit") or 10)))

    raise ValueError(f"неизвестный инструмент: {name}")


def respond(msg_id, result=None, error=None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        msg_id = msg.get("id")
        if method == "initialize":
            respond(msg_id, {
                "protocolVersion": msg.get("params", {}).get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "spriteanim-studio", "version": "0.1"},
            })
        elif method in ("notifications/initialized", "notifications/cancelled"):
            continue
        elif method == "ping":
            respond(msg_id, {})
        elif method == "tools/list":
            respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name") or ""
            args = params.get("arguments") or {}
            try:
                result = call_tool(name, args)
                text = json.dumps(result, ensure_ascii=False, indent=1)
                respond(msg_id, {"content": [{"type": "text", "text": text}]})
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")
                respond(msg_id, {"content": [{"type": "text", "text": body}], "isError": True})
            except Exception as exc:  # noqa: BLE001
                respond(msg_id, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                                 "isError": True})
        elif msg_id is not None:
            respond(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
