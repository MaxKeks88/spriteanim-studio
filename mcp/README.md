MCP для SpriteAnim Studio
=========================

`studio_mcp.py` — локальный MCP-сервер (stdio, без зависимостей). Он не хранит
состояние, а проксирует вызовы в запущенное приложение `http://127.0.0.1:8189`.

Инструменты:

| Инструмент | Что делает |
|---|---|
| `studio_status` | ComfyUI, модели, активные задания |
| `generate_image` | картинка Qwen Image 2.1 (промпт, размер, формат, шаги, seed) |
| `generate_animation` | анимация по картинке персонажа (промпт, кадры, размер) |
| `remove_background` | PNG с прозрачностью |
| `agent_prompt` | локальный агент пишет промпт |
| `job_status` / `wait_job` | статус и ожидание задания |
| `list_runs` | последние прогоны |

## Claude Code

```
claude mcp add spriteanim -- python "E:\SpriteAnim Studio\mcp\studio_mcp.py"
```

или в `.mcp.json` проекта:

```json
{
  "mcpServers": {
    "spriteanim": {
      "command": "python",
      "args": ["E:\\SpriteAnim Studio\\mcp\\studio_mcp.py"]
    }
  }
}
```

## Codex

В `~/.codex/config.toml`:

```toml
[mcp_servers.spriteanim]
command = "python"
args = ["E:\\SpriteAnim Studio\\mcp\\studio_mcp.py"]
```

## VS Code (GitHub Copilot)

VS Code 1.147 читает MCP-серверы в формате `mcpServers` из двух файлов:

- **для всех проектов** — `%USERPROFILE%\.copilot\mcp-config.json`;
- **для одного проекта** — `.mcp.json` в корне папки, которую открыли.

```json
{
  "mcpServers": {
    "spriteanim": {
      "type": "stdio",
      "command": "python",
      "args": ["E:\\SpriteAnim Studio\\mcp\\studio_mcp.py"],
      "tools": ["*"]
    }
  }
}
```

Порядок в VS Code:

1. Открыть чат (Ctrl+Alt+I) и выбрать в переключателе сессии **Copilot**
   (нужен вход в GitHub Copilot).
2. Выполнить **Chat: Open Customizations → MCP Servers** — сервер `spriteanim`
   появится в списке. При первом запуске VS Code спросит доверие к серверу.
3. Спросить, например: «Покажи статус SpriteAnim Studio» — в ответе должен быть
   вызов `studio_status`, а не пересказ.

Если сервер не появился: **Developer: Reload Window** (конфигурация читается при
старте сессии) или **MCP: List Servers** → посмотреть вывод сервера.

Старый `.vscode/mcp.json` с ключом `servers` относится к устаревшему Local-харнессу
и для Copilot-сессии не нужен.

## Установленная версия

Скрипт лежит рядом с программой:
`%LOCALAPPDATA%\Programs\SpriteAnimStudio\_internal\mcp\studio_mcp.py`.

## Требования

- Приложение должно быть запущено (окно или `Запуск.vbs`): без него MCP вернёт
  ошибку соединения.
- Python 3.10+ в PATH (у установленной версии можно указать путь к встроенному
  интерпретатору из `_internal`, если он есть).

Пример сессии:

```
agent → generate_image {"prompt": "рыжий кот на подоконнике", "size": 1024}
studio → {"id": "…", "state": "queued"}
agent → wait_job {"id": "…", "timeout_sec": 300}
studio → {"state": "done", "outputs": [{"filename": "img_00001.png", …}]}
```
