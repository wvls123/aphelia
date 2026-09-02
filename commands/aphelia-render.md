---
name: aphelia-render
description: Перерендерить существующий run Aphelia после правок storyboard (renderer → guardian)
---

# /aphelia-render <slug>

Для уже существующего `aphelia-memory/runs/<slug>/` с готовыми `script.txt`, `assets/vo-words.json`, `storyboard.json`:

1. **Task**(`aphelia-storyboarder`) — только если пользователь просил изменить сторибоард (иначе пропустить).
2. **Task**(`aphelia-renderer`) — `render.py` (музыка генерируется, если `bgm-generated.mp3` ещё нет).
3. **Task**(`aphelia-guardian`) — PASS/FIX; при FIX — луп storyboarder → renderer → guardian (≤ 2).
4. Ответ: путь к `out/<slug>.mp4`, длительность, контакт-лист.
