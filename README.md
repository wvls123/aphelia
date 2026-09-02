# Framepro — Reels Factory (Cursor-плагин)

Из любой информации (ссылка, новость, тема, текст) — готовый вертикальный Reels **60–90 с**: research → сценарий-история (Gemini) → озвучка **Qwen3-TTS** с ударениями → стикмен-вырезки → сторибоард, где режиссёр-агент сам выбирает стиль, музыку, звуки и эффекты из каталога Remotion (или пишет свой компонент) → оригинальная музыка **ACE-Step** → рендер **Remotion** → QA → метаданные. Оркестратор запускает субагентов **волнами параллельно**.

## Установка

**Cursor Marketplace:** Customize → Plugins → поиск **Framepro**. Имя в каталоге: `Framepro — Reels Factory` (`framepro`). После ревью Cursor ставится отсюда: [github.com/Horosheff/framepro](https://github.com/Horosheff/framepro).

Пока плагин на проверке — локально:

```powershell
.\install-plugin.ps1        # копирует в %USERPROFILE%\.cursor\plugins\local\framepro, ставит npm-зависимости, клонирует ACE-Step (uv sync)
# и регистрирует субагентов в .cursor/agents + %USERPROFILE%\.cursor\agents (без этого Task их не видит)
# перезапустить Cursor → Customize → Plugins → Framepro; в чате /framepro-new
```

Требования: Python 3.12+ с `qwen-tts`, `openai-whisper`, `ruaccent`, `rembg`, `torch`/`torchaudio` (CUDA), `soundfile`, `Pillow`; Node 20+; `uv` (для ACE-Step); `ffmpeg`/`ffprobe` в PATH; GPU ≥ 12 ГБ (Qwen3-TTS 1.7B, ACE-Step 2B turbo).

## Использование

```
/framepro-new https://postium.ru/...  --duration 75
/framepro-new Alibaba показала видеомодель со звуком за один проход
```

Директор (основной агент) выполняет `rules/framepro-orchestrator.mdc`:

| Волна | Агенты | Параллель |
|---|---|---|
| 1 | `framepro-researcher` | — |
| 2 | `framepro-writer` — **Gemini 3.1 Pro**, `shared/story-playbook.md` | — |
| 3 | `framepro-voice` ‖ `framepro-illustrator` ×2–3 ‖ `framepro-screencaster` | **да** |
| 4 | `framepro-storyboarder` — анализ ролика, стиль-пресет, `music-brief.json`, SFX по смыслу, эффекты/`custom` | — |
| 5 | `framepro-renderer` — `render.py`: музыка ACE-Step → Remotion → loudnorm | — |
| 6 | `framepro-guardian` ‖ `framepro-publisher` | **да** |
| фикс | storyboarder → renderer → guardian (≤ 2 круга) | — |
| 7 | `framepro-fixic` (если были инциденты) | — |

Результат: `framepro-memory/runs/<slug>/out/<slug>.mp4` (1080×1920, −14 LUFS, faststart) + `qa/contact.jpg` + `publish.md`.

Другие команды: `/framepro-voice` (перепроектировать фирменный голос), `/framepro-render <slug>` (перерендер после правок).

## Что внутри

```text
.cursor-plugin/plugin.json   манифест Cursor Plugin
rules/                       оркестратор (волны, Gemini для сценариста, разнообразие), только русский
agents/  skills/             10 субагентов и их инструкции
commands/                    /framepro-new, /framepro-voice, /framepro-render
shared/                      story-playbook, remotion-capabilities, motion-library (стиль-пресеты, архетипы),
                             storyboard-schema, music-contract, voice-contract, image-style, memory-protocol, pitfalls
scripts/                     init_run, script_check, voice, cutout, merge_assets, capture_web, validate_storyboard,
                             timeline, music (ACE-Step), sync_remotion, render, qa, audio_manifest
templates/remotion/          Remotion 4.0.520: @remotion/transitions (slide/wipe/fade/flip/clockWipe/iris + custom
                             zoom/flash/slice), @remotion/captions (TikTok-страницы), @remotion/layout-utils (fitText),
                             @remotion/paths (evolvePath), @remotion/motion-blur (CameraMotionBlur, Trail), @remotion/noise
                             (handheld), @remotion/shapes, @remotion/media-utils (waveform), @remotion/lottie, spring();
                             src/custom/ — компоненты, которые пишет агент
templates/audio/             186 SFX с семантическими тегами (sfx-catalog.json) + 6 запасных BGM (Mixkit Free License)
templates/fonts/  stickers/  Inter/Neucha локально; библиотека вырезок + _style-reference.png
voices/narrator-ru/          фирменный голос (VoiceDesign → референс для клона)
vendor/ace-step/             ACE-Step 1.5 (клонируется установщиком, gitignore)
framepro-memory/runs/<slug>/ память прогонов (см. shared/memory-protocol.md)
```

## Ключевые решения

- **Один движок — Remotion**, собранный из официальных пакетов, а не ручных кривых. Каталог того, что доступно агенту: `shared/remotion-capabilities.md`. Если эффекта нет — агент пишет `custom/<Name>.tsx` по контракту `CustomLayerProps`, `tsc` проверяет.
- **Вариативность от ролика к ролику**: стиль-пресет (цвет акцента, стиль субтитров, словарь переходов) не повторяет предыдущий; музыка генерируется под настроение; SFX подбираются по словам сценария из каталога; валидатор ловит повторы.
- **Музыка без страйков**: ACE-Step 1.5 (MIT, обучен на лицензированных/royalty-free данных, коммерческое использование разрешено) генерирует уникальный трек на каждый ролик. Библиотека Mixkit — запасной вариант.
- **Голос**: Qwen3-TTS 12Hz-1.7B (актуальное семейство). VoiceDesign проектирует живого диктора, Base клонирует. Ударения: ruaccent → U+0301 только на словах из `stress-overrides.json`; маркированный дубль принимается, если Whisper слышит его идеально. Подробности — `shared/voice-contract.md`.
- **Сценарист — Gemini 3.1 Pro** с драматургическим playbook (один рассказчик, повороты, польза в речи, анти-паттерны).

## Ручной запуск без агентов (отладка)

```powershell
python scripts/init_run.py --slug demo --topic "..." --source https://...
# script.json → python scripts/script_check.py --project framepro-memory/runs/demo --from-json
python scripts/voice.py narrate --project framepro-memory/runs/demo
python scripts/cutout.py --project framepro-memory/runs/demo
# storyboard.json + music-brief.json → python scripts/validate_storyboard.py --project framepro-memory/runs/demo
python scripts/render.py --project framepro-memory/runs/demo
python scripts/qa.py --project framepro-memory/runs/demo
```

Референсы: `youtube-to-claude-agent-v5.mp4`, `youtube-to-claude-agent-v6-cartoon.mp4`; разбор — `docs/reference-breakdown.md`.
