---
name: aphelia-voice
description: Озвучка Aphelia — Qwen3-TTS клон фирменного голоса, ударения ruaccent→U+0301, проверка Whisper + MMS forced alignment; выход vo.mp3, vo-words.json, voice-report.json.
---

# Aphelia Voice

Вход: `<run>/script.txt`, `stress-overrides.json` (если есть), `voices/narrator-ru/`. Выход: `assets/vo.mp3`, `assets/vo.wav`, `assets/vo-words.json`, `assets/vo-duration.txt`, `voice-report.json`, `fragments/voice.md`.

Прочитай `shared/voice-contract.md`.

## Шаги

1. Проверь голос: `voices/narrator-ru/ref.wav` и `ref.txt` существуют. Если нет — `python scripts/voice.py design-voice --name narrator-ru` (6 дублей VoiceDesign, выбирается чистый и быстрый; ~2 мин).
2. Озвучь: `python scripts/voice.py narrate --project <run>`. Параметры по умолчанию: tempo 1.06, gap 0.12, tries 3, min-sim 0.74, `--marks overrides` (метки из **ruaccent** на словах `qwen_force_marks` / `ruaccent_custom_dict` + `stress-overrides.json` ролика; первый дубль всегда чистый, маркированный заменяет его лишь при sim ≥ 0.97 и целом слове). Бренды в кириллице перед моделью переписываются в латиницу. GPU занята другим процессом → подожди, не запускай второй экземпляр. В PowerShell не оборачивай в `2>&1 | Tee-Object` — предупреждения torchaudio/Whisper дают ложный exit code 1; читай последнюю JSON-строку.
3. Прочитай итог: `duration`, `doubtful_stress`, `marks_mode`. Сделай `python scripts/dump_takes.py <run>/voice-report.json` и просмотри `voice-report.txt`: строки `BAD` = предложения, где лучший дубль всё равно ниже порога — перечисли их во фрагменте с `heard`. Числительные в любом падеже и латинские аббревиатуры `normalize()` уже вырезает/транслитерирует; если `heard` отличается от текста только цифрами/латиницей — аудио в порядке, это не BAD.
4. Длительность vs `brief.json` (`min_seconds…max_seconds`): в диапазоне — ✅; иначе ⚠️ и во фрагменте точная рекомендация Директору: «сократить на ~N слов» или «добавить ~N слов» (2.35 слова/с). Не ускоряй аудио сильнее 1.12 — голос станет неестественным.
5. Ударения: MMS-оценка (`doubtful_stress`) — **advisory**, ~80 % точности на омографах, глайд принимает за ударение. Решай по `heard` Whisper, а не по stress. Если ключевое слово реально услышано неверно — добавь **слово** в `qwen_force_marks` (позицию `+` возьмёт ruaccent) или форму в `ruaccent_custom_dict`, если библиотека не знает заимствование; для одного ролика — `stress-overrides.json`. Перезапусти narrate **один раз**. Если чистый дубль переврал смысловой омограф («дели́ работу» → «де́ли») — перезапуск с `--marks homographs`. Остальные сомнительные слова просто перечисли. Метки на обычных словах и известных брендах не нужны — они дают глайд («Алибоюбы»).
6. Слова, которые модель ломает в каждом дубле («два-ка» → «два козы»), — не лечить метками: во фрагменте предложи writer переформулировку.

## Фрагмент

`=== VOICE ===`, status, outputs, `summary`: duration, words, sentences, сколько дублей BAD (и сколько из них — только цифры/латиница), список doubtful_stress, marks_mode, темп (слов/с). `incident_report`: зависания модели, падения CUDA OOM, дубли > 3, систематический глайд в маркированных дублях.

