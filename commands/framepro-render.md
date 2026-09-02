---
name: framepro-render
description: Перерендерить существующий run Framepro после правок storyboard (renderer → guardian)
---

# /framepro-render <slug>

Для уже существующего `framepro-memory/runs/<slug>/` с готовыми `script.txt`, `assets/vo-words.json`, `storyboard.json`:

1. **Task**(`framepro-storyboarder`) — только если пользователь просил изменить сторибоард (иначе пропустить).
2. **Task**(`framepro-renderer`) — `render.py` (музыка генерируется, если `bgm-generated.mp3` ещё нет).
3. **Task**(`framepro-guardian`) — PASS/FIX; при FIX — луп storyboarder → renderer → guardian (≤ 2).
4. Ответ: путь к `out/<slug>.mp4`, длительность, контакт-лист.
