# Кастомные ноды ComfyUI / Custom ComfyUI nodes

Две ноды, которые использует воркфлоу анимации SpriteAnim Studio. Без них
воркфлоу не загрузится в ComfyUI. Модели не скачиваются, всё считается на CPU.

Two nodes used by the SpriteAnim Studio animation workflow. Without them the
workflow will not load in ComfyUI. No model downloads; everything runs on CPU.

## Установка / Install

Скопируйте папку `sprite_anim_nodes` в каталог пользовательских нод ComfyUI:

```
<ComfyUI>\custom_nodes\sprite_anim_nodes\
    __init__.py
    loop_trim.py
```

Затем перезапустите ComfyUI. В меню нод появятся:

- **Sprite: Remove Background + Edge Cleanup** (`Sprite / Background`);
- **Sprite: Keep One Loop** (`Sprite / Animation`).

Copy the `sprite_anim_nodes` folder into `<ComfyUI>\custom_nodes\` and restart
ComfyUI.

Требования: `numpy`, `scipy`, `torch` — они уже есть в ComfyUI.
Requirements: `numpy`, `scipy`, `torch` — already bundled with ComfyUI.

## SpriteChromaKey

Убирает ровный цветной фон (пурпурный, зелёный, синий) и чистит кайму.
Возвращает **straight-alpha RGBA** и маску (1 = непрозрачный объект).

| Параметр | Что делает |
|---|---|
| `key_color` | цвет подложки: magenta / green / blue |
| `sample_border` | измерить фактический цвет по краям кадра (объект не должен касаться края) |
| `clip_black` | поднять, чтобы убрать дымку; слишком высоко — съест тонкие детали |
| `clip_white` | опустить, чтобы больше объекта стало полностью непрозрачным |
| `despill` | убрать цвет фона из полупрозрачных краёв |
| `choke_px` | сжать маску в пикселях исходника (0,2–0,5 если остаётся кайма) |
| `edge_bleed_px` | продлить цвет объекта под прозрачные пиксели, чтобы не было бахромы |

Работает по одному кадру, чтобы не раздувать память на 1024p.

## SpriteLoopTrim

Оставляет ровно один цикл или одно действие из сгенерированного клипа.

| Параметр | Что делает |
|---|---|
| `mode` | `cycle` — один цикл ходьбы/бега; `action` — одна атака от стойки до стойки |
| `max_frames` | 0 — все кадры цикла; иначе не больше N кадров, равномерно по циклу |
| `dedupe_twos` | убрать дубли, если клип отрендерен «на двойках» |
| `min_frames` | минимальная длина цикла, короче — не принимать |

Возвращает кадры, их число и текстовое пояснение (сколько убрано и почему).
