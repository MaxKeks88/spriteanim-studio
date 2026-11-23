# SpriteAnim Studio — настольное окно

Отдельное приложение вместо вкладки браузера. `server.py` поднимается в фоне,
интерфейс `ui/index.html` показывается в собственном окне через
**pywebview 6 + Microsoft Edge WebView2**: без адресной строки, вкладок и
браузерных меню. Закрыли окно — процесс завершился.

```
desktop/
├── main.py               точка входа: сервер + окно
├── build.py              сборка PyInstaller → dist/SpriteAnimStudio/
├── SpriteAnimStudio.iss  установщик Inno Setup 6
├── version_info.txt      свойства .exe (версия 0.4.2)
├── icon.ico              иконка окна, .exe и установщика
├── requirements.txt      pywebview
├── run.bat               запуск из исходников без консоли
└── README.md
```

## Требования

- Windows 10/11 x64.
- Microsoft Edge WebView2 Runtime — в Windows 11 и обновлённой Windows 10 уже есть.
- Для запуска из исходников — Python 3.11+; один пакет:

```
python -m pip install -r desktop/requirements.txt
```

## Запуск из исходников

```
python desktop/main.py
```

или двойной клик по `desktop\run.bat` (через `pythonw`, без консоли; лог —
`.cache/studio.log`).

Переменные для диагностики:

| Переменная | Что делает |
|---|---|
| `SPRITE_DEBUG=1` | DevTools, контекстное меню, статус-бар WebView2 |
| `SPRITE_SMOKE=1` | скрытое окно, грузит UI и само закрывается — проверка сборки |
| `SPRITE_PORT=...` | другой порт (по умолчанию 8189) |

## Сборка и установка

```
python -m pip install pyinstaller
python desktop/build.py
```

Результат — `desktop/dist/SpriteAnimStudio/` (≈37 МБ): `SpriteAnimStudio.exe`,
`_internal/` с ресурсами, иконка и version-info. Рядом при первом запуске
создаются `.cache/`, `output/`, `voice/` (модели) и `.profile/` (WebView2).

Установщик:

```
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" desktop\SpriteAnimStudio.iss
```

Результат — `desktop/dist/SpriteAnimStudio-Setup-0.4.2.exe` (≈13 МБ).

Готовый установщик лежит в `Install\` в корне проекта
(`SpriteAnimStudio-Setup-0.4.2.exe`).

- ставится в `%LOCALAPPDATA%\Programs\SpriteAnimStudio` — без прав администратора,
  папка доступна на запись;
- AppId тот же, что у версии 0.1, поэтому установка 0.2 заменяет старую;
- ярлык в меню «Пуск», по желанию — на рабочем столе;
- при удалении сохраняются `.cache` (настройки), `output` (результаты) и
  `voice` (скачанные модели); профиль WebView2 и лог удаляются.

## Как устроено

1. `main.py` ставит `SPRITE_NO_BROWSER=1`, чтобы `server.py` не открывал браузер,
   и запускает `server.serve()` в фоновом потоке.
2. Окно создаётся сразу со splash-экраном; когда порт 8189 отвечает, туда
   загружается интерфейс. Если сервер не поднялся за 40 с — экран ошибки
   с кнопкой «Повторить».
3. `CoreWebView2.PermissionRequested` разрешает микрофон (голосовой ввод),
   в том числе если WebView2 инициализируется уже после старта окна.
4. Закрытие окна вызывает `server.shutdown_app()` — гасятся агент и сервер.
   Если сервер уже работал до запуска (второй экземпляр), окно подключается
   к нему и при закрытии его не гасит.
5. Скачивания включены (`ALLOW_DOWNLOADS`), внешние ссылки открываются
   в системном браузере (`OPEN_EXTERNAL_LINKS_IN_BROWSER`), профиль WebView2
   лежит в `.profile` рядом с `.exe` и переживает перезапуск.
6. Если WebView2 недоступен, включается запасной путь — Edge/Chrome в режиме
   `--app`, как в старом `app.py`.

В собранной версии `server.py` берёт ресурсы из `_internal` (PyInstaller
`_MEIPASS`), а `.cache`, `output` и `voice` пишет рядом с `.exe` — это уже
учитывается в `server.py` (`DATA` / `ROOT`).

## Проверено

- запуск из исходников: окно открывается, UI загружается, `/api/*` отвечают
  (ComfyUI 0.46.0 online), закрытие завершает процесс и освобождает порт;
- PyInstaller-сборка: smoke-тест (`SPRITE_SMOKE=1`) завершается с кодом 0,
  страница и API работают, окно отрисовано (снят скриншот);
- разрешение микрофона подключается без ошибок (полный голосовой прогон
  в окне не повторялся);
- установщик 0.2 собран и **проверен поверх установленной 0.1**: та же папка,
  версия .exe 0.2.1, ярлык в «Пуск», приложение открывается и работает;
- в установщик не попадают `.profile`, `.cache` и `output` из папки сборки
  (`Excludes` в `.iss`) — иначе вместе с программой уезжал бы профиль WebView2
  с машины разработчика весом ~11 МБ;
- метка версии в интерфейсе — `v0.2`.

## Старое

`app.py`, `build/build.py` и `build/SpriteAnimStudio.iss` остаются для
браузерного запуска Edge/Chrome `--app`. Актуальная настольная версия — эта папка.
