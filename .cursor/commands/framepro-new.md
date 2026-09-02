---
name: framepro-new
description: Запустить полный прогон Framepro — из темы/ссылки/текста собрать Reels 60–90 с (research → сценарий Gemini → озвучка ‖ картинки ‖ скринкаст → сторибоард с музыкой и эффектами → рендер Remotion → QA ‖ метаданные)
---

# /framepro-new <тема | URL | текст> [--duration 75]

Директор (основной агент) выполняет `rules/framepro-orchestrator.mdc`:

1. **Write** `.cursor/framepro-handoff.md` ← `# Framepro — новая сессия`.
2. `python scripts/init_run.py --slug <slug-из-темы> --topic "<тема>" --source <url>… --duration <N>`.
3. Голос: при отсутствии `voices/narrator-ru/ref.wav` — `python scripts/voice.py design-voice --name narrator-ru`.
4. Волны Task: 1 researcher → 2 writer (**gemini-3.1-pro**) → 3 **voice ‖ illustrator×2–3 ‖ screencaster** → 4 storyboarder (анализ, стиль-пресет, музыка, звуки, эффекты/custom) → 5 renderer (музыка ACE-Step + Remotion) → 6 **guardian ‖ publisher** → фикс-луп ≤ 2 → 7 fixic при инцидентах.
5. Ответ: путь к `framepro-memory/runs/<slug>/out/<slug>.mp4`, длительность, контакт-лист картинкой, 3 заголовка, стиль-пресет и музыка.

Slug: латиница, дефисы, ≤ 30 символов (`dreamx-creator`). Длительность по умолчанию 75 с (диапазон 60–95).
