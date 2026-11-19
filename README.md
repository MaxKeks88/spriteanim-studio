# SpriteAnim Studio

Локальное приложение для Windows, которое превращает картинку персонажа в
спрайтовые анимации: генерирует изображения и кадры через **ComfyUI**, убирает
фон, собирает спрайт-листы и устанавливает анимации в **Godot 4** и **Unity**.
Интерфейс полностью переводится на **русский и английский** язык.

A local Windows app that turns a character image into sprite animations: it
generates images and frames with **ComfyUI**, removes backgrounds, builds sprite
sheets and installs animations into **Godot 4** and **Unity**. The whole UI is
available in **Russian and English**.

---

## Возможности / Features

| Русский | English |
|---|---|
| **Изображения** — генерация по промпту, до 5 референсов, форматы 1:1, 16:9, 9:16, 4:3, 3:4 | **Images** — generate from a prompt, up to 5 reference images, 1:1, 16:9, 9:16, 4:3, 3:4 |
| **Убрать фон** — прозрачный PNG одной кнопкой | **Remove background** — transparent PNG in one click |
| **Анимация** — спрайтовый цикл или одно действие, выбор цвета подложки, обрезка кадра, видео и кадры PNG | **Animation** — sprite loop or one-shot, backdrop color, frame trimming, video and PNG frames |
| **Спрайт-лист** — встроенный редактор: сетка, поля, выравнивание, установка в Godot 4 и Unity | **Sprite sheet** — built-in editor: grid, padding, alignment, install into Godot 4 or Unity |
| **Промпт агентом** — локальная модель пишет промпт по вашему описанию и видит исходную картинку | **Prompt with agent** — a local model writes the prompt from your brief and can see the source image |
| **Голосовой ввод** — русская модель GigaAM v3, работает локально (скачивается из настроек) | **Voice input** — Russian GigaAM v3 model, runs locally (downloaded from Settings) |
| **История** — все прогоны с параметрами и кнопкой «Повторить» | **History** — every run with parameters and a Repeat button |
| **MCP-сервер** — Claude Code, Codex, VS Code и другие агенты могут управлять приложением | **MCP server** — Claude Code, Codex, VS Code and other agents can drive the app |
| **Обновления** — приложение проверяет новые версии на GitHub; жёлтая кнопка у «Настройки» и установка в один клик | **Updates** — checks GitHub for new versions; a yellow button next to Settings and one-click install |
| **Три темы** — тёмная фиолетовая, палитра Sprite Sheet Maker, светлая бордовая | **Three themes** — dark violet, Sprite Sheet Maker palette, light burgundy |

Интерфейс: переключатель **RU / EN** в шапке рядом с «Настройки». Язык
запоминается, редактор спрайт-листа переключается вместе с приложением.

UI language: the **RU / EN** switch in the header next to Settings. The choice is
remembered, and the sprite-sheet editor follows the app language.

---

## Требования / Requirements

- **Windows 10/11 x64**. Окно приложения — WebView2 (в Windows 11 уже есть).
- **ComfyUI должен быть запущен до приложения** — на `127.0.0.1:8188`.
  Без него не работают ни вкладки, ни генерация.
- Модели скачиваются из **Настройки → Модели** (Qwen Image 2.1, MiniMax H3,
  агент Gemma 4 12B). Нужны свободные ~60 ГБ и видеопамять под модели.
- Голосовой ввод необязателен: движок и модель (278 МБ) скачиваются из
  **Настройки → Голосовой ввод**.

- **Windows 10/11 x64**. The app window uses WebView2 (included in Windows 11).
- **ComfyUI must be running before you start the app** — on `127.0.0.1:8188`.
  Without it neither the tabs nor generation work.
- Models are downloaded from **Settings → Models** (Qwen Image 2.1, MiniMax H3,
  the Gemma 4 12B agent). Expect ~60 GB of disk and enough VRAM.
- Voice input is optional: the engine and model (278 MB) are downloaded from
  **Settings → Voice input**.

---

## Установка / Install

В папке **`Install`** лежит готовый установщик:

```
Install\SpriteAnimStudio-Setup-0.2.0.exe
```

1. Запустите его — права администратора не нужны, ставится в профиль пользователя.
2. Установите (ярлык появится в меню «Пуск»).
3. **Сначала запустите ComfyUI**, затем откройте **SpriteAnim Studio**.
4. В настройках скачайте недостающие модели, при желании — голос.

The ready-to-use installer is in the **`Install`** folder:

```
Install\SpriteAnimStudio-Setup-0.2.0.exe
```

1. Run it — no administrator rights are needed, it installs into your user profile.
2. Finish the installation (a Start menu shortcut is created).
3. **Start ComfyUI first**, then open **SpriteAnim Studio**.
4. In Settings, download any missing models and optionally the voice model.

### Запуск из исходников / Run from source

```
python -m pip install -r desktop/requirements.txt
python desktop/main.py
```

Нужен Python 3.11+. Настольное окно: `desktop/main.py`, старый браузерный
запуск: `Запуск.vbs`.

Python 3.11+ is required. Desktop window: `desktop/main.py`; the old
browser-based launcher: `Запуск.vbs`.

### Сборка установщика / Build the installer

```
python desktop/build.py
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" desktop\SpriteAnimStudio.iss
```

Результат — `desktop/dist/SpriteAnimStudio-Setup-0.2.0.exe`.

Output: `desktop/dist/SpriteAnimStudio-Setup-0.2.0.exe`.

---

## Обновления / Updates

Приложение при запуске проверяет последний релиз на GitHub. Если версия новее,
рядом с «Настройки» появляется **круглая жёлтая кнопка со стрелкой**; она
открывает **Настройки → 5. Обновление**. Там же кнопки «Проверить обновление»
и «Скачать и установить»: приложение скачивает установщик из релиза, запускает
его и перезапускается.

Чтобы выпустить обновление: поднимите `APP_VERSION` в `server.py`, соберите
установщик и создайте релиз с тегом `vX.Y.Z`, приложив
`SpriteAnimStudio-Setup-X.Y.Z.exe`. Приложение читает `/releases/latest`.

On startup the app checks the latest GitHub release. If a newer version exists,
a **round yellow arrow button** appears next to Settings; it opens
**Settings → 5. Update**. The same section has “Check for updates” and
“Download and install”: the app downloads the installer from the release, runs
it and restarts.

To publish an update: bump `APP_VERSION` in `server.py`, build the installer and
create a release tagged `vX.Y.Z` with `SpriteAnimStudio-Setup-X.Y.Z.exe`
attached. The app reads `/releases/latest`.

---

## MCP для агентов / MCP for agents

`mcp/studio_mcp.py` — stdio-сервер, который проксирует вызовы в запущенное
приложение. Инструменты: `studio_status`, `generate_image`,
`generate_animation`, `remove_background`, `agent_prompt`, `job_status`,
`wait_job`, `list_runs`. Подключение к Claude Code, Codex и VS Code —
в [mcp/README.md](mcp/README.md).

`mcp/studio_mcp.py` is a stdio server that proxies calls into the running app.
Tools: `studio_status`, `generate_image`, `generate_animation`,
`remove_background`, `agent_prompt`, `job_status`, `wait_job`, `list_runs`.
Setup for Claude Code, Codex and VS Code is in [mcp/README.md](mcp/README.md).

---

## Структура / Layout

```
server.py          HTTP-сервер, графы ComfyUI, агент, голос, настройки
ui/                интерфейс: index.html, sheet.html, i18n.js
sheet_py/          бэкенд редактора спрайт-листа (Godot/Unity)
desktop/           настольное окно (pywebview + WebView2), сборка, .iss
mcp/               MCP-сервер и инструкции
voice/             обвязка голосового ввода (движок и модель скачиваются)
assets/ prompts/ workflows/ skills/   данные для генерации и агента
docs/              проектная документация
Install/           готовый установщик
```

---

## Лицензия / License

Лицензия пока не выбрана. Если планируете использовать код в своих проектах,
напишите в issue — добавим подходящую (например, MIT).

No license has been chosen yet. If you want to reuse the code, open an issue and
we will add a suitable license (for example MIT).
