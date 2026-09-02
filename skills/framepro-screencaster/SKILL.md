---
name: framepro-screencaster
description: Скринкастер Framepro — Playwright-запись плавной прокрутки страниц-источников в mp4 для вставки «рамка браузера» (доказательство). Параллельно с voice и illustrator.
---

# Framepro Screencaster

Вход: `brief.json.sources`, `research.md` (какие страницы — первоисточники). Выход: `assets/videos/<name>.mp4` (1–3 клипа по 6–10 с), `assets/videos.json`, `fragments/screencaster.md`.

## Шаги

1. Выбери 1–3 URL, которые зритель должен «увидеть своими глазами»: официальное заявление, статья на русском, репозиторий. Приоритет — русскоязычная страница с заголовком по теме.
2. Для каждого: `python scripts/capture_web.py --project <run> --url <url> --name <short> --seconds 8`. Имя — латиницей коротко (`habr`, `openai-blog`).
3. Проверь кадр: `ffmpeg -ss 2 -i assets/videos/<name>.mp4 -frames:v 1 qa/shot-<name>.jpg` и посмотри (Read): страница загрузилась, нет баннера cookies поверх текста, заголовок читаем. Если баннер — повтори с `--seconds 10` (скрипт кликает «Принять»/«Accept») или выбери другой URL.
4. Запиши `assets/videos.json`: `[{"name": "habr", "rel": "videos/habr.mp4", "url": "habr.com/…", "duration": 8.2, "what": "статья на Хабре с заголовком …"}]` — `url` пойдёт в адресную строку рамки.

## Правила

- Не записывать страницы с логином/пейволлом.
- Не дольше 10 с на клип — в ролике будет 3–6 с.

## Фрагмент

`=== SCREENCASTER ===`, status, outputs, summary, `incident_report` (таймауты, Playwright не установлен → `npm install` в `scripts/node`, `npx playwright install chromium`).
