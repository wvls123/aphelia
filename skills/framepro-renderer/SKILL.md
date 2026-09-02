---
name: framepro-renderer
description: Рендер Framepro — render.py (Remotion): timeline → музыка ACE-Step (если bgm-generated) → sync → npx remotion render → loudnorm → out/<slug>.mp4; проверка длительности, LUFS/TP, ошибок tsc.
---

# Framepro Renderer

Вход: `<run>/storyboard.json`, `music-brief.json` (если музыка генерируется), `custom/*.tsx` (если есть). Выход: `out/<slug>.mp4`, `assets/audio/bgm-generated.mp3` + `music-report.json` (при генерации), `fragments/renderer.md`.

## Шаги

1. Из корня плагина: `python scripts/render.py --project <run>` (block_until_ms ≥ 900000). Скрипт сам: `timeline.py` → копирует SFX → генерирует музыку через `uv run --directory vendor/ace-step python scripts/music.py` (первый запуск скачивает модель ACE-Step ~5 ГБ, 3–10 мин; дальше ~30–60 с) → `sync_remotion.py` (data.ts, public/, custom-компоненты, реестр) → `npx remotion render` → ffmpeg loudnorm −14 LUFS + лимитер −1 dBTP → `out/<slug>.mp4`.
2. Проверь: `ffprobe -v error -show_entries format=duration:stream=width,height,codec_name -of json out/<slug>.mp4` → 1080×1920, h264, длительность = `timeline.duration` ± 0.2; `ffmpeg -hide_banner -i out/<slug>.mp4 -af ebur128=peak=true -f null -` → Integrated −16…−12, True peak ≤ −1.
3. Ошибки:
   - `tsc`/сборка Remotion падает на `src/custom/<Name>.tsx` — это код сторибордера: **не правь сам**, верни Директору точный текст ошибки (инцидент medium, `role: storyboarder`).
   - Ошибка в `src/layers.tsx`/`Scene.tsx`/`Reel.tsx` — инцидент high (движок), с текстом.
   - `music.py` упал (нет `uv`, нет GPU, OOM) — инцидент medium; временно поставь в storyboard библиотечный трек (`audio/tech-house.mp3` и т.п.) **только по команде Директора**.
   - `missing asset` — путь в storyboard не совпадает с файлом в `assets/` → инцидент для storyboarder.
4. Не правь storyboard, шрифты, цвета.

## Фрагмент

`=== RENDERER ===`, status, outputs (путь, длительность, размер, LUFS/TP, музыка: сгенерирована/библиотека, seed), время рендера, `incident_report`.
