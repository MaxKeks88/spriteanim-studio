# Правила для агентов в этой папке

Это приложение — `SpriteAnim Studio`: форма над ComfyUI, которая делает спрайтовую
анимацию из картинки персонажа, плюс встроенный редактор листов с установкой
в Godot 4 и Unity.

**Сначала прочитайте `docs/PROJECT.md`** — там устройство, решения и что уже
проверено. Не перечитывайте код целиком и не пересматривайте решения, которые там
записаны, без причины. План следующих работ — `docs/PLAN.md`.

Коротко:

- Студия: `server.py` + `ui/index.html`, Python stdlib, порт 8189. Запуск без консоли —
  `Запуск.vbs` (pythonw, лог в `.cache/studio.log`), остановка — `Остановить.vbs`
  (`POST /api/quit`), отладка с выводом — `run-console.bat`.
- Настольное окно: `desktop/main.py` (pywebview + Edge WebView2), сборка —
  `desktop/build.py`, установщик — `desktop/SpriteAnimStudio.iss`. Старые `app.py`
  и `build/` — браузерный `--app`.
- Редактор спрайт-листа: серверная часть `sheet_py/`, клиент `ui/sheet.html`,
  отдаётся по `/sheet`; Node и отдельный порт больше не нужны.
- Интерфейс переводится на русский и английский: словарь `ui/i18n.js`,
  переключатель RU/EN в шапке; язык хранится в `.cache/settings.json` (`lang`).
- Воркфлоу: `workflows/*.json` (UI-формат ComfyUI). Новый режим = новый файл.
- Параметры ищутся по типу ноды, а не по номеру.
- `widgets_values` главнее `widgets_values_named`.
- Кадры только `17k + 5`, размер кратен 32, цвет подложки связан с промптом.
- Оригиналы пользователя (рабочие папки на Desktop, его проекты) не трогать.
- После изменения поведения — обновить `docs/PROJECT.md` (разделы 6, 8, 9).

Проверка после правок:

```powershell
cd "E:\SpriteAnim Studio"; python server.py --check
node -e "const fs=require('fs');const s=fs.readFileSync('E:/SpriteAnim Studio/ui/index.html','utf8');new Function(s.match(/<script>([\s\S]*)<\/script>/)[1]);console.log('ui ok')"
```
