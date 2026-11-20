# Сторонние компоненты / Third-party components

SpriteAnim Studio использует или запускает компоненты, у которых свои лицензии.
The app uses or runs components with their own licenses.

## Не входят в сборку / Not bundled

- **ComfyUI** — сервер генерации. Ставится отдельно самим пользователем,
  приложение общается с ним по HTTP. Лицензия: GPL-3.0
  (https://github.com/comfyanonymous/ComfyUI). Мы не распространяем ComfyUI.
- **Модели** — скачиваются пользователем из указанных репозиториев и работают по
  лицензиям своих авторов:
  - Qwen Image 2.1 — https://huggingface.co/Comfy-Org/Qwen-Image-2.1 ;
  - MiniMax H3 — https://huggingface.co/Comfy-Org/MiniMax-H3 ;
  - Gemma 4 12B — https://huggingface.co/unsloth/gemma-4-12b-it-GGUF
    (Gemma Terms of Use);
  - Real-ESRGAN anime 6B — https://huggingface.co/ximso/RealESRGAN_x4plus_anime_6B
    (архитектура Real-ESRGAN — BSD-3-Clause).
  Перед коммерческим использованием проверьте условия каждой модели.
- **Godot** и **Unity** — только целевые движки для установки листа; в поставку
  не входят.

## Входят в сборку / Bundled

- **pywebview** — BSD-3-Clause.
- **pythonnet** — MIT.
- **clr_loader** — MIT.
- **PyInstaller** — GPL-2.0-or-later с исключением для загрузчика;
  собранное приложение не обязано быть GPL.
- **transcribe.cpp** и **GigaAM v3** (голосовой ввод) — MIT; полный текст и
  сведения о компонентах: `voice/LICENSE.txt` и `voice/lib/licenses/`.

## Тексты и программы в репозитории / Texts and programs in the repository

- **`skills/`** — тексты скиллов из приложения Minimax H3 Workspace, скопированы
  по решению владельца проекта. Права принадлежат их авторам; эти тексты не
  покрываются MIT-лицензией SpriteAnim Studio.
- **`sheet/`** (Sprite Sheet Maker) — исходники встроенного редактора листов.
  Права принадлежат автору программы; не покрываются MIT-лицензией
  SpriteAnim Studio.

Если вы правообладатель и хотите уточнить упоминание или убрать материал —
откройте issue в репозитории проекта.
If you are a rights holder and want a mention corrected or material removed,
please open an issue in the project repository.
