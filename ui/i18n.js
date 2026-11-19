/* SpriteAnim Studio — переводы интерфейса.
 *
 * Устроено просто: ключ — русский текст, значение — английский. Переводится
 * не разметка, а готовый текст в DOM (и атрибуты placeholder/title), поэтому
 * новые элементы переводить отдельно не нужно — достаточно добавить пару.
 *
 * Динамические строки с числами («25 шагов», «3 из 5») обрабатывают правила
 * SUBS ниже. Пользовательский текст (промпты, пути, имена файлов) не трогаем.
 */
(function () {
  const EN = {
    // ---------- шапка и вкладки ----------
    "Изображения": "Images",
    "Убрать фон": "Remove background",
    "Анимация": "Animation",
    "Спрайт-лист": "Sprite sheet",
    "История": "History",
    "История прогонов": "Run history",
    "Настройки": "Settings",
    "⚙ Настройки": "⚙ Settings",
    "🕘 История": "🕘 History",
    "очередь:": "queue:",
    "Очередь пуста": "Queue is empty",
    "ComfyUI: проверяю…": "ComfyUI: checking…",
    "ComfyUI работает": "ComfyUI is running",
    "ComfyUI не отвечает": "ComfyUI is not responding",
    "ComfyUI не запущен": "ComfyUI is not running",
    "ComfyUI вернул ошибку": "ComfyUI returned an error",
    "ComfyUI запускается — это займёт несколько секунд": "ComfyUI is starting — this takes a few seconds",
    "ComfyUI не отвечает — запустите его и обновите страницу": "ComfyUI is not responding — start it and reload the page",
    "не запущен": "not running",
    "установите ComfyUI, чтобы работали все вкладки": "install ComfyUI to enable all tabs",

    // ---------- общие кнопки ----------
    "Отмена": "Cancel",
    "Закрыть": "Close",
    "✕ Закрыть": "✕ Close",
    "Открыть": "Open",
    "Открыть папку": "Open folder",
    "↗ Открыть папку": "↗ Open folder",
    "↻ Обновить": "↻ Refresh",
    "↻ Проверить снова": "↻ Check again",
    "↻ Ещё вариант": "↻ Another variant",
    "↺ По умолчанию": "↺ Default",
    "↺ Стандартная": "↺ Standard",
    "По умолчанию": "Default",
    "Применить": "Apply",
    "Повторить": "Repeat",
    "↻ Повторить": "↻ Repeat",
    "повторить": "repeat",
    "повторить удачный": "repeat successful",
    "Убрать": "Remove",
    "Собрать": "Assemble",
    "Сгенерировать": "Generate",
    "Стоп": "Stop",
    "■ Стоп": "■ Stop",
    "▶ Запустить ComfyUI": "▶ Start ComfyUI",
    "⤓ Скачать и установить": "⤓ Download and install",
    "⧉ Скопировать итоговый": "⧉ Copy final prompt",
    "⬇ PNG с прозрачностью": "⬇ Transparent PNG",
    "⬇ Видео mp4": "⬇ Video mp4",
    "⬇ Кадры PNG (zip)": "⬇ PNG frames (zip)",
    "🎲 Новый": "🎲 New",
    "📁 Выбрать": "📁 Choose",
    "📁 Выбрать папку…": "📁 Choose folder…",
    "📎 Загрузить исходник": "📎 Load source",
    "✨ Промпт агентом": "✨ Prompt with agent",
    "✨ думаю…": "✨ thinking…",
    "Нажмите, чтобы остановить": "Click to stop",

    // ---------- вкладка «Изображения» ----------
    "Модель": "Model",
    "Исходник": "Source",
    "Что делать с исходником": "What to do with the source",
    "Изменить это": "Edit this",
    "правка картинки": "edit image",
    "Новое по образцу": "New from reference",
    "другой персонаж": "another character",
    "Без исходника генерация идёт по промпту.": "Without a source, generation follows the prompt.",
    "Параметры": "Parameters",
    "Формат": "Aspect",
    "Размер": "Size",
    "Размер результата": "Result size",
    "Результат": "Result",
    "Шаги": "Steps",
    "быстрее": "faster",
    "стандарт": "standard",
    "крупнее": "larger",
    "меньше": "smaller",
    "обычно": "normal",
    "чище": "cleaner",
    "быстро": "fast",
    "Seed": "Seed",
    "Случайный": "Random",
    "случайный": "random",
    "каждый раз": "every time",
    "каждый раз новый": "new every time",
    "Фиксированный": "Fixed",
    "повторить": "repeat",
    "свой:": "custom:",
    "Исходный": "Original",
    "как загрузили": "as loaded",
    "≈1 МП": "≈1 MP",
    "Здесь появятся картинки: промпт и результат друг под другом.": "Images appear here: prompt and result, one under the other.",
    "Историю можно листать.": "You can scroll the history.",
    "Опишите картинку: кто, что делает, где, свет и стиль": "Describe the image: who, what they do, where, light and style",
    "Напишите, что нарисовать": "Describe what to draw",
    "Очистить промпт": "Clear prompt",

    // ---------- вкладка «Убрать фон» ----------
    "Картинка с фоном": "Image with background",
    "PNG / JPG, любой фон": "PNG / JPG, any background",
    "Перетащите картинку": "Drop an image",
    "или нажмите, чтобы выбрать файл": "or click to choose a file",
    "Модель оставляет объект, а фон делает прозрачным (Qwen Image 2.1).": "The model keeps the subject and makes the background transparent (Qwen Image 2.1).",
    "Здесь появится результат: картинка с прозрачным фоном.": "The result appears here: an image with a transparent background.",
    "Инструкция — в поле ниже, его можно не трогать.": "The prompt is in the field below; you can leave it as is.",
    "Прозрачность настоящая (альфа-канал), без «белого фона»: такой PNG сразу годится и для генерации, и для редактора.": "The transparency is real (alpha channel), not a white background: the PNG works for generation and in the editor.",
    "Фон убран — добавлено в ленту": "Background removed — added to the feed",

    // ---------- вкладка «Анимация» ----------
    "Персонаж": "Character",
    "Перетащите картинку персонажа": "Drop a character image",
    "PNG / JPG, вид сбоку, всё тело в кадре": "PNG / JPG, side view, whole body in frame",
    "Прозрачный фон не нужен: генерация идёт на ровной пурпурной подложке.": "A transparent background is not needed: generation runs on a flat magenta backdrop.",
    "Что происходит": "What is happening",
    "Название движения": "Motion name",
    "для папки и файлов": "for the folder and files",
    "Можно по-русски — в имени папки станет латиницей.": "You can write in Russian — the folder name becomes Latin.",
    "Как повторяется": "How it loops",
    "Цикл": "Loop",
    "цикл": "loop",
    "ходьба, бег, дыхание — повторяется": "walk, run, breathing — loops",
    "Один раз": "Once",
    "один раз": "once",
    "атака, смерть — от стойки до стойки": "attack, death — one-shot",
    "От этого зависит, как обрезать готовый ролик: один бесшовный цикл или одно действие от стойки до стойки.": "This decides how the clip is trimmed: one seamless loop or a single action from idle to idle.",
    "Размер кадра": "Frame size",
    "Округляется до кратного 32. Больше 768 — дольше и рискованнее по видеопамяти.": "Rounded to a multiple of 32. Above 768 is slower and needs more video memory.",
    "Длительность": "Duration",
    "Модель считает кадрами: 24 fps, длина = 17k + 5. Ползунок стоит только на допустимых значениях — 124 кадра ≈ 5,2 с (по умолчанию из воркфлоу).": "The model works in frames: 24 fps, length = 17k + 5. The slider only stops at valid values — 124 frames ≈ 5.2 s (workflow default).",
    "Цвет подложки": "Backdrop color",
    "Пурпурный": "Magenta",
    "Зелёный": "Green",
    "Синий": "Blue",
    "пурпурный": "magenta",
    "зелёный": "green",
    "синий": "blue",
    "Это цвет фона в самом видео: под него настраивается вырезка, и он же подставляется в промпт. После рендера фон становится прозрачным.": "This is the video background color: keying is tuned for it and it is inserted into the prompt. After rendering the background becomes transparent.",
    "Дополнительно: ключ, кромка, обрезка цикла": "Advanced: key, edge, loop trim",
    "clip_black (убрать дымку)": "clip_black (cut haze)",
    "clip_white (плотность)": "clip_white (density)",
    "choke (сжать маску, px)": "choke (shrink mask, px)",
    "edge_bleed (подложить край, px)": "edge_bleed (bleed edge, px)",
    "Обрезка кадров (0 = все)": "Frame trim (0 = all)",
    "убирать дубли («на двойках»)": "remove duplicates (\"on twos\")",
    "Трогайте только если остаётся кайма или фон не убирается полностью.": "Touch these only if a fringe remains or the background is not fully removed.",
    "Промпт и ключ должны называть один цвет — иначе фон вырежется плохо.": "The prompt and the key must name the same color — otherwise keying is poor.",
    "Здесь появится результат: видео, кадры с прозрачностью и спрайт-лист.": "The result appears here: video, transparent frames and a sprite sheet.",
    "Промпт движения — в поле ниже.": "The motion prompt is in the field below.",
    "Изображение": "Image",
    "Картинка": "Image",
    "Видео": "Video",
    "видео": "video",
    "без промпта": "no prompt",
    "Картинка готова — добавлена в ленту": "Image is ready — added to the feed",
    "Картинка перенесена в «Анимацию»": "Image moved to \"Animation\"",
    "Картинка перенесена в «Убрать фон»": "Image moved to \"Remove background\"",
    "→ В анимацию": "→ To animation",
    "→ Собрать в редакторе": "→ Open in editor",
    "Что агент увидел в исходной картинке": "What the agent saw in the source image",
    "Исходник не используется: агент опишет стиль словами, модель нарисует новое.": "The source is not used: the agent describes the style in words and the model draws something new.",
    "Модель возьмёт исходник и изменит его по промпту: лицо, поза и фон сохраняются.": "The model takes the source and changes it by the prompt: face, pose and background are kept.",
    "Эта модель рисует с нуля: исходник останется подсказкой для агента. Править картинку умеют Qwen Image 2.1 и MiniMax H3 Image.": "This model draws from scratch: the source only guides the agent. Qwen Image 2.1 and MiniMax H3 Image can edit images.",
    "Ползунок стоит только на допустимых значениях — 124 кадра ≈ 5,2 с (по умолчанию из воркфлоу).": "The slider only stops at valid values — 124 frames ≈ 5.2 s (workflow default).",

    // ---------- прогресс и статусы ----------
    "в очереди": "queued",
    "В очереди ComfyUI…": "Queued in ComfyUI…",
    "отправляю в ComfyUI…": "sending to ComfyUI…",
    "рисую": "drawing",
    "Рисую…": "Drawing…",
    "вырезаю фон": "removing background",
    "Вырезаю фон…": "Removing background…",
    "собираю кадры": "assembling frames",
    "Генерация: сэмплинг и сборка кадров…": "Generating: sampling and assembling frames…",
    "готовлю кадры…": "preparing frames…",
    "читаю кадры: 0 из 0…": "reading frames: 0 of 0…",
    "Готово": "Done",
    "Останавливаю…": "Stopping…",
    "работаю": "working",
    "думаю…": "thinking…",
    "проверяю…": "checking…",
    "проверяю промпт…": "checking prompt…",
    "подготовка…": "preparing…",
    "распаковка…": "unpacking…",
    "считается": "processing",
    "Задание пропало из очереди": "The job disappeared from the queue",
    "Незавершённые задания восстановлены": "Unfinished jobs restored",
    "Параметры прогона подставлены": "Run parameters applied",
    "Ошибка:": "Error:",
    "ошибка": "error",
    "ошибка агента": "agent error",
    "ошибка загрузки": "download error",
    "неизвестно": "unknown",

    // ---------- лента и история ----------
    "Все": "All",
    "Изображений пока нет.": "No images yet.",
    "Анимаций пока нет.": "No animations yet.",
    "загружаю…": "loading…",
    "Пока пусто. Сгенерируйте что-нибудь —": "Nothing yet. Generate something —",
    "прогоны появятся здесь с параметрами и кнопкой «Повторить».": "runs will appear here with their parameters and a \"Repeat\" button.",
    "Убрать фон": "Remove background",
    "В анимацию": "To animation",
    "Крупно": "Enlarge",
    "PNG с прозрачностью": "Transparent PNG",
    "Инструкция": "Prompt",
    "Промпт": "Prompt",
    "Открыть": "Open",
    "Не удалось открыть прогон:": "Could not open the run:",
    "Не удалось перенести:": "Could not move:",
    "Этот прогон не найден в истории ComfyUI": "This run was not found in ComfyUI history",
    "Прошлый прогон не найден в очереди ComfyUI": "The previous run was not found in the ComfyUI queue",
    "Не удалось прочитать кадры:": "Could not read frames:",
    "В редакторе:": "In the editor:",
    "редактор не запустился": "the editor did not start",
    "Сначала сгенерируйте анимацию": "Generate an animation first",

    // ---------- настройки ----------
    "Куда сохранять": "Save folder",
    "Готовые картинки, фон и анимации копируются сюда, по подпапкам": "Finished images, background cutouts and animations are copied here, into subfolders",
    "Путь можно менять прямо в строке: вставьте и нажмите Enter. Папка и подпапки создадутся сами.": "You can edit the path right in the field: paste it and press Enter. The folder and its subfolders are created automatically.",
    "Выбрать папку…": "Choose folder…",
    "Выбрать эту папку": "Choose this folder",
    "Открыть папку": "Open folder",
    "Этот компьютер": "This PC",
    "Тема": "Theme",
    "Оформление приложения и встроенного редактора спрайт-листа.": "Appearance of the app and the built-in sprite sheet editor.",
    "Тёмная фиолетовая": "Dark violet",
    "Sprite Sheet Maker": "Sprite Sheet Maker",
    "Светлая бордовая": "Light burgundy",
    "ComfyUI": "ComfyUI",
    "Официальный сайт": "Official site",
    "↗ Официальный сайт": "↗ Official site",
    "Скачать и установить": "Download and install",
    "Проверить снова": "Check again",
    "Модели": "Models",
    "Папка моделей": "Models folder",
    "Папка агента": "Agent folder",
    "Где искать модели и куда их скачивать. Если выбрали свою папку — ComfyUI должен её знать (добавьте путь в его настройки папок).": "Where models live and where to download them. If you pick your own folder, ComfyUI must know about it (add the path in its folder settings).",
    "Папка сохранения": "Save folder",
    "Скачать недостающие": "Download missing",
    "Проверить микрофон": "Check microphone",
    "Проверяю микрофон…": "Checking microphone…",
    "Куда скачается:": "Download to:",
    "моделей нет": "no models",
    "папок нет": "no folders",
    "Всего моделей:": "Models total:",
    "Не установлено": "Not installed",
    "Не хватает файлов": "Missing files",
    "Не хватает:": "Missing:",
    "Не хватает для Qwen Image 2.1:": "Missing for Qwen Image 2.1:",
    "Чего не хватает:": "Missing:",
    "Внимание:": "Warning:",
    "Добавится в конец автоматически:": "Added to the end automatically:",
    "В промпте уже есть": "The prompt already has",
    "нужный фон и технические ограничения — ничего не добавляю.": "the required background and technical constraints — nothing to add.",
    "есть": "yes",
    "нет": "no",
    "✓ есть": "✓ yes",
    "✕ нет": "✕ no",
    "Не удалось прочитать настройки": "Could not read settings",
    "Обновление": "Update",
    "При запуске приложение проверяет новые версии на GitHub. Обновление скачивает установщик и перезапускает приложение.": "On startup the app checks for new versions on GitHub. Updating downloads the installer and restarts the app.",
    "↻ Проверить обновление": "↻ Check for updates",
    "⤓ Скачать и установить": "⤓ Download and install",
    "Что нового": "What's new",
    "Доступно обновление": "Update available",
    "скачиваю…": "downloading…",
    "устанавливаю…": "installing…",
    "нет связи с GitHub": "no connection to GitHub",
    "Обновление:": "Update:",
    "не удалось проверить:": "could not check:",
    "не удалось скачать обновление": "could not download the update",
    "Не удалось получить состояние установки": "Could not read the setup state",
    "Это ровно тот текст, который уйдёт в модель.": "This is exactly the text sent to the model.",
    "⧉ Скопировать итоговый": "⧉ Copy final prompt",
    "Итоговый промпт скопирован": "Final prompt copied",
    "не удалось сохранить": "failed to save",
    "не удалось открыть папку": "failed to open folder",
    "не удалось начать загрузку": "failed to start download",
    "не удалось начать установку": "failed to start installation",
    "не удалось запустить": "failed to start",
    "не удалось поставить задание": "failed to queue the job",
    "не удалось проверить промпт": "failed to check the prompt",
    "не удалось подготовить кадры": "failed to prepare frames",
    "нет данных о моделях": "no model data",
    "нет воркфлоу в папке workflows": "no workflow in the workflows folder",
    "пока не поддерживается": "not supported yet",
    "по умолчанию": "default",

    // ---------- группы установки (сервер) ----------
    "Генерация картинок и удаление фона": "Image generation and background removal",
    "Основная модель для вкладок «Картинка» и «Убрать фон». Скачиваются диффузионная модель (int8), текстовый инкодер Qwen3-VL 8B и VAE.": "Main model for the Images and Remove background tabs. Downloads the diffusion model (int8), the Qwen3-VL 8B text encoder and the VAE.",
    "диффузионная модель, int8": "diffusion model, int8",
    "текстовый инкодер Qwen3-VL 8B": "Qwen3-VL 8B text encoder",
    "MiniMax H3 — анимация": "MiniMax H3 — animation",
    "Спрайтовые анимации (ходьба, атака)": "Sprite animations (walk, attack)",
    "Модель для вкладки «Анимация». Скачиваются видео-модель, текстовый инкодер Qwen3-VL 32B и видео-VAE.": "Model for the Animation tab. Downloads the video model, the Qwen3-VL 32B text encoder and the video VAE.",
    "видео-модель MiniMax H3": "MiniMax H3 video model",
    "текстовый инкодер Qwen3-VL 32B": "Qwen3-VL 32B text encoder",
    "видео-VAE": "video VAE",
    "Агент (Gemma 4 12B)": "Agent (Gemma 4 12B)",
    "Пишет промпты и видит картинки": "Writes prompts and sees images",
    "Локальный агент для кнопки «Промпт агентом»: модель Gemma 4 12B (Q4_0), визуальный проектор и сборка llama.cpp. Работает без интернета.": "Local agent for the \"Prompt with agent\" button: the Gemma 4 12B model (Q4_0), a vision projector and the llama.cpp build. Works offline.",
    "модель агента, Q4_0": "agent model, Q4_0",
    "визуальный проектор — агент видит картинки": "vision projector — lets the agent see images",
    "движок для агента": "agent engine",
    "Голосовой ввод (GigaAM v3)": "Voice input (GigaAM v3)",
    "Распознавание речи для промптов": "Speech recognition for prompts",
    "Необязательно: без него кнопки микрофона нет. Русская модель GigaAM v3 (MIT) и движок transcribe.cpp (MIT) работают локально — звук никуда не отправляется.": "Optional: without it there is no microphone button. The Russian GigaAM v3 model (MIT) and the transcribe.cpp engine (MIT) run locally — audio never leaves the machine.",
    "transcribe.cpp (движок)": "transcribe.cpp (engine)",
    "распаковка в voice/lib (Windows, CPU+Vulkan)": "unpacked into voice/lib (Windows, CPU+Vulkan)",
    "русская модель распознавания, Q8_0": "Russian speech model, Q8_0",
    "качество, 25 шагов": "quality, 25 steps",
    "Голосовой ввод": "Voice input",
    "Голосовая модель не установлена — скачайте её в настройках": "The voice model is not installed — download it in Settings",

    // ---------- микрофон ----------
    "Голос:": "Voice:",
    "Микрофон:": "Microphone:",
    "микрофон:": "microphone:",
    "микрофон: доступен ✓": "microphone: available ✓",
    "Остановить запись": "Stop recording",
    "Слишком короткая запись": "Recording is too short",
    "Не расслышал — попробуйте ещё раз": "Didn't catch that — try again",
    "не удалось распознать": "failed to recognize",
    "Разрешите доступ к микрофону в браузере": "Allow microphone access in the browser",
    "Запрашиваю доступ к микрофону…": "Requesting microphone access…",
    "браузер не видит микрофон": "the browser cannot see a microphone",
    "браузер не даёт доступ к микрофону": "the browser denies microphone access",
    "браузер не ответил на запрос доступа": "the browser did not answer the access request",
    "браузер не показал окно разрешения — разрешите микрофон в настройках сайта (замок слева от адреса)": "the browser showed no permission prompt — allow the microphone in the site settings (lock icon next to the address)",
    "доступ к микрофону запрещён — разрешите его в настройках сайта": "microphone access is blocked — allow it in the site settings",
    "микрофон запрещён для этого сайта — нажмите на замок в адресной строке и разрешите": "the microphone is blocked for this site — click the lock in the address bar and allow it",
    "Браузер ждёт разрешения на микрофон — посмотрите на адресную строку": "The browser is waiting for microphone permission — check the address bar",
    "Браузер не дал доступ к буферу — выделите текст вручную": "The browser blocked clipboard access — select the text manually",
    "getUserMedia нет": "getUserMedia is unavailable",
    "«Настройки сайта» → «Микрофон» → «Разрешить», обновите страницу.": "\"Site settings\" → \"Microphone\" → \"Allow\", then reload the page.",
    "В Windows также: Параметры → Конфиденциальность → Микрофон → разрешить приложениям.": "On Windows also: Settings → Privacy → Microphone → allow apps.",
    "Если окно разрешения не появилось: нажмите на значок сайта (замок) слева от адреса →": "If no permission prompt appeared: click the site icon (lock) next to the address →",
    "устройств ввода:": "input devices:",
    "Впишите ширину и высоту от 256": "Enter width and height, 256 or more",
    "ширина": "width",
    "высота": "height",
    "Не удалось прочитать состояние:": "Could not read state:",
    "Опишите в двух словах, что нужно": "Describe briefly what you need",
    "Опишите движение словами": "Describe the motion in words",
    "Промпт пустой": "Prompt is empty",
    "Первая картинка правится, остальные — референсы: стиль, детали, второй ракурс.": "The first image is edited, the rest are references: style, details, another angle.",
    "Сначала загрузите картинку": "Load an image first",
    "Сначала загрузите картинку персонажа": "Load a character image first",
    "Нужен файл изображения": "An image file is required",
    "Модель не вернула картинку": "The model returned no image",
    "Нет готовой модели изображений в ComfyUI.": "No ready image model in ComfyUI.",
    "Проверьте папки models файлового хранилища ComfyUI.": "Check the models folders of the ComfyUI storage.",
    "Слишком большой кадр: максимум 1536": "Frame is too large: maximum is 1536",
    "НЕ защищённый": "NOT secure",
    "защищённый": "secure",
    "Воркфлоу:": "Workflow:",
    "ноды ComfyUI": "ComfyUI nodes",
    "· агент:": "· agent:",
    "· папка моделей:": "· models folder:",
    "· по исходнику": "· from source",
    "агент не ответил": "the agent did not respond",
    "Агент:": "Agent:",
    "Остановлено — текст оставлен как есть": "Stopped — the text is kept as is",
    "Не выбран тип повтора": "Repeat type is not selected",
    "как в исходной картинке": "same as the source image",
    "исходный размер": "original size",
    "Пропорции — из загруженной картинки; «Исходный» не меняет размер.": "Aspect comes from the loaded image; \"Original\" keeps the size.",
    "Для папки и файлов": "For the folder and files",
    "Папок нет": "No folders",
    "На уровень выше": "Up one level",
    "Увеличить": "Zoom in",
    "Увеличить (+)": "Zoom in (+)",
    "Уменьшить (−)": "Zoom out (−)",
    "Масштаб 1:1": "Scale 1:1",
    "Вписать в экран (0)": "Fit to screen (0)",
    "Закрыть (Esc)": "Close (Esc)",
    "По умолчанию — папка моделей ComfyUI": "Default — the ComfyUI models folder",
    "Предыдущий": "Previous",
    "Следующий": "Next",
    "например 20261023": "e.g. 20261023",
    "папка агента": "agent folder",
    "папка моделей ComfyUI": "ComfyUI models folder",
    "Вписать": "Fit",
    "масштаб": "scale",
    "колонок": "columns",
    "вписано": "fit",
    "авто": "auto",
    "черновик": "draft",
    "правка картинки": "edit image",
    "убирать дубли («на двойках»)": "remove duplicates (\"on twos\")",
    "Ходьба (цикл)": "Walk (loop)",
    "цикл шага, бесшовно повторяется": "walk cycle, loops seamlessly",
    "Атака (действие)": "Attack (one-shot)",
    "один удар: от стойки до возврата в стойку": "one strike: from idle back to idle",
    "Language / Язык": "Language",
    "Русский": "Russian",
    "Фон": "Background",
    "Что делает персонаж: движение, ракурс, темп. Можно по-русски.": "What the character does: motion, angle, pacing. Russian is fine.",
    "версия": "version",
    "из": "of",
    "кадр не загрузился": "frame failed to load",
    "контекст:": "context:",
    "нет:": "missing:",
    "разрешение:": "resolution:",
    "символов": "characters",
    "фиксированный": "fixed",
    "шагов": "steps",
    "— и в промпте тоже": "— and in the prompt too",
    "— нажмите, чтобы увеличить": "— click to enlarge",
    "— откройте «Настройки»": "— open Settings",
    "📎 Добавить исходник": "📎 Add source",
    "diffusion-модель": "diffusion model",
    "output\\SpriteAnim\\<название>\\<прогон>": "output\\SpriteAnim\\<name>\\<run>",
    "Здесь лежат модель Gemma, её визуальный проектор и llama.cpp.": "The Gemma model, its vision projector and llama.cpp live here.",
    "Кадры в zip — с прозрачностью (выход узла RGBA). В ComfyUI они лежат в": "Frames in the zip are transparent (RGBA node output). In ComfyUI they are in",
    "Лист собирается в браузере из кадров с прозрачностью — по одному кадру в ячейке.": "The sheet is assembled in the browser from transparent frames — one frame per cell.",
    "Приложение работает поверх ComfyUI — он считает картинки, фон и анимацию. Если ComfyUI ещё не установлен, скачайте его с официального сайта или поставьте готовую сборку автоматически (≈ 2 ГБ, распаковка в папку программы).": "The app runs on top of ComfyUI, which computes images, cutouts and animation. If ComfyUI is not installed yet, download it from the official site or install a ready build automatically (≈ 2 GB, unpacked into the app folder).",
    "При запуске приложение проверяет, что нужные модели лежат на месте. Ниже — что скачивается и сколько места занимает. Файлы кладутся в папку моделей, после скачивания перезапустите ComfyUI, чтобы он их увидел.": "On startup the app checks that the required models are in place. Below is what is downloaded and how much space it takes. Files go into the models folder; after downloading, restart ComfyUI so it sees them.",
    "Это цвет фона в самом видео: под него настраивается вырезание, и он же подставляется в промпт. После рендера фон становится прозрачным.": "This is the video background color: keying is tuned for it and it is inserted into the prompt. After rendering the background becomes transparent.",

  };

  // Правила для строк с числами и составных строк.
  const SUBS = [
    [/^Доступно обновление (.+)$/, "Update $1 available"],
    [/^версия (.+) · установлена последняя$/, "version $1 · up to date"],
    [/^версия (.+) · доступна (.+)$/, "version $1 · $2 available"],
    [/^версия (.+) · релизов пока нет$/, "version $1 · no releases yet"],
    [/^не удалось проверить: (.+)$/, "could not check: $1"],
    [/^Обновление (.+) скачано — установщик запущен$/, "Update $1 downloaded — installer started"],
    [/^Обновление: /, "Update: "],
    [/· папка моделей:/g, "· models folder:"],
    [/· агент:/g, "· agent:"],
    [/·\s*цикл(?![\wА-Яа-яЁё])/g, "· loop"],
    [/⤓ Скачать недостающие/g, "⤓ Download missing"],
    [/^(\d+)×(\d+) · свой$/, "$1×$2 · custom"],
    [/^(\d+)×(\d+), ячейка (\d+)×(\d+), лист (\d+)×(\d+) px\.$/, "$1×$2, cell $3×$4, sheet $5×$6 px."],
    [/·\s*PNG с альфой/g, "· PNG with alpha"],
    [/\/с(?![\wА-Яа-яЁё])/g, "/s"],
    [/^Больше (\d+) картинок не нужно$/, "No more than $1 images"],
    [/^Готово: /, "Done: "],
    [/^В редакторе: /, "In the editor: "],
    [/^Промпт готов · скилл: /, "Prompt ready · skill: "],
    [/^без скилла$/, "no skill"],
    [/^Первая картинка правится, остальные \((\d+)\) — референсы: стиль, детали, второй ракурс\.$/, "The first image is edited, the other $1 are references: style, details, another angle."],
    [/^как в исходной · (.+)$/, "same as source · $1"],
    [/^Лист получится (\d+)×(\d+) — больше (\d+) px по высоте\. Выберите масштаб меньше\.$/, "The sheet would be $1×$2 — more than $3 px high. Choose a smaller scale."],
    [/^читаю кадры: (\d+) из (\d+)…$/, "reading frames: $1 of $2…"],
    [/^Цвет подложки: /, "Backdrop color: "],
    [/^(\d+) кадров$/, "$1 frames"],
    [/^(\d+) кадра$/, "$1 frames"],
    [/^(\d+) кадр$/, "$1 frame"],
    [/(\d+) кадров/g, "$1 frames"],
    [/(\d+) кадра/g, "$1 frames"],
    [/(\d+) кадр(?![\wА-Яа-яЁё])/g, "$1 frame"],
    [/^(\d+) шагов$/, "$1 steps"],
    [/(\d+) шагов/g, "$1 steps"],
    [/^(\d+) символов$/, "$1 characters"],
    [/^кадров: (\d+)$/, "$1 frames"],
    [/^шагов: (\d+)$/, "$1 steps"],
    [/(\d+) из (\d+)/g, "$1 of $2"],
    [/^из (\d+)$/, "of $1"],
    [/^по исходнику \((\d+)\)$/, "from source ($1)"],
    [/^по исходнику$/, "from source"],
    [/(\d+),(\d+)\s+ГБ/g, "$1.$2 GB"],
    [/(\d+),(\d+)\s+МБ/g, "$1.$2 MB"],
    [/(\d+),(\d+)\s+КБ/g, "$1.$2 KB"],
    [/ГБ/g, "GB"],
    [/МБ/g, "MB"],
    [/КБ/g, "KB"],
    [/(\d+),(\d+)\s+с(?![\wА-Яа-яЁё])/g, "$1.$2 s"],
    [/(\d+)\s+с(?![\wА-Яа-яЁё])/g, "$1 s"],
    [/^версия /, "version "],
    [/^≈(\d+)\s*МП$/, "≈$1 MP"],
    [/МП/g, "MP"]
  ];

  const SKIP = [
    "textarea", "input", "select", "option", "script", "style", "code", "pre",
    "[data-no-i18n]", ".msg-text", ".run-prompt", ".dir-list", "#dirPath",
    "#comfyPath", ".set-path", ".setup-path"
  ].join(",");
  // Атрибуты (placeholder/title) есть и у полей ввода — их переводим.
  const ATTR_SKIP = [
    "script", "style", "code", "pre", "[data-no-i18n]", ".dir-list",
    "#dirPath", "#comfyPath", ".set-path", ".setup-path"
  ].join(",");

  const ATTRS = ["placeholder", "title", "aria-label"];
  const CYR = /[А-Яа-яЁё]/;
  const origText = new WeakMap();
  const origAttr = new WeakMap();
  let lang = "ru";

  const norm = (s) => s.replace(/\s+/g, " ").trim();

  function lookup(raw) {
    const key = norm(raw);
    if (!key) return null;
    if (Object.prototype.hasOwnProperty.call(EN, key)) return EN[key];
    let out = key;
    for (const [re, rep] of SUBS) out = out.replace(re, rep);
    return out !== key ? out : null;
  }

  function translateText(node) {
    const raw = node.nodeValue;
    if (!raw || !CYR.test(raw)) return;
    let out = lookup(raw);
    if (out == null) return;
    if (out === raw.trim()) return;
    const lead = (raw.match(/^\s*/) || [""])[0];
    const trail = (raw.match(/\s*$/) || [""])[0];
    origText.set(node, raw);
    node.nodeValue = lead + out + trail;
  }

  function restoreText(node) {
    const raw = origText.get(node);
    if (raw != null) { node.nodeValue = raw; origText.delete(node); }
  }

  function translateAttr(el, name) {
    const val = el.getAttribute(name);
    if (!val || !CYR.test(val)) return;
    const out = lookup(val);
    if (out == null || out === val) return;
    let map = origAttr.get(el);
    if (!map) { map = {}; origAttr.set(el, map); }
    if (!(name in map)) map[name] = val;
    el.setAttribute(name, out);
  }

  function restoreAttr(el, name) {
    const map = origAttr.get(el);
    if (map && name in map) { el.setAttribute(name, map[name]); delete map[name]; }
  }

  function eachText(root, fn) {
    if (!root) return;
    if (root.nodeType === 3) {
      const p = root.parentElement;
      if (p && p.closest(SKIP)) return;
      fn(root);
      return;
    }
    if (root.nodeType !== 1) return;
    if (root.closest(SKIP)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const p = node.parentElement;
      if (p && p.closest(SKIP)) continue;
      fn(node);
    }
  }

  function eachAttr(root, fn) {
    if (!root) return;
    if (root.nodeType !== 1) return;
    if (!root.closest(ATTR_SKIP)) {
      for (const name of ATTRS) fn(root, name);
    }
    if (!root.querySelectorAll) return;
    for (const el of root.querySelectorAll("[placeholder],[title],[aria-label]")) {
      if (el.closest(ATTR_SKIP)) continue;
      for (const name of ATTRS) fn(el, name);
    }
  }

  function applyAll() {
    eachText(document.body, translateText);
    eachAttr(document.body, translateAttr);
  }

  function restoreAll() {
    eachText(document.body, restoreText);
    eachAttr(document.body, restoreAttr);
    origText && void 0;
  }

  const observer = new MutationObserver((records) => {
    if (lang !== "en") return;
    for (const rec of records) {
      if (rec.type === "characterData") {
        translateText(rec.target);
      } else if (rec.type === "childList") {
        for (const node of rec.addedNodes) {
          if (node.nodeType === 3) translateText(node);
          else if (node.nodeType === 1) { eachText(node, translateText); eachAttr(node, translateAttr); }
        }
      } else if (rec.type === "attributes") {
        translateAttr(rec.target, rec.attributeName);
      }
    }
  });

  function observe() {
    observer.observe(document.body, {
      subtree: true, childList: true, characterData: true,
      attributes: true, attributeFilter: ATTRS
    });
  }

  function set(next) {
    lang = next === "en" ? "en" : "ru";
    document.documentElement.lang = lang;
    if (lang === "en") applyAll(); else restoreAll();
  }

  window.AppI18N = {
    get lang() { return lang; },
    set,
    apply: applyAll,
    tr: lookup,
    observe
  };

  // Показываем переводы сразу после разбора разметки — до загрузки настроек.
  // Окончательный язык применит boot() по сохранённой настройке.
  if ((navigator.language || "").toLowerCase().startsWith("ru")) {
    lang = "ru";
  } else {
    lang = "en";
    document.documentElement.lang = "en";
    applyAll();
  }
  observe();
})();
