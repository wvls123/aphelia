---
name: aphelia-new
description: Запустить полный прогон Aphelia — из темы/ссылки/текста собрать Reels 60–90 с (research → сценарий Gemini → озвучка ‖ картинки ‖ скринкаст → сторибоард с музыкой и эффектами → рендер Remotion → QA ‖ метаданные)
---

# /aphelia-new <тема | URL | текст> [--duration 75]

Если после команды **нет** темы, ссылки или текста — спроси одно: «Кинь тему, ссылку или текст — из чего собирать Reels?» и остановись. Не придумывай тему (в том числе «контент-завод», MCP, Wordstat). Не переключай workspace.

Директор выполняет `rules/aphelia-orchestrator.mdc` **в текущей папке**:

1. **Write** `.cursor/aphelia-handoff.md` ← `# Aphelia — новая сессия`.
2. `python <PLUGIN_ROOT>/scripts/init_run.py --slug <slug-из-темы> --topic "<тема пользователя>" --source <url>… --duration <N>`.
3. Голос: при отсутствии `<PLUGIN_ROOT>/voices/narrator-ru/ref.wav` — `python <PLUGIN_ROOT>/scripts/voice.py design-voice --name narrator-ru`.
4. Волны Task: 1 researcher (**gemini-3.7-flash-high**) → 2 writer (**gemini-3.7-flash-high**) → 3 **voice ‖ illustrator×2–3 (все GenerateImage, без копирования stickers) ‖ screencaster** → 4 storyboarder (анализ, стиль-пресет, музыка, звуки, эффекты/custom) → 5 renderer (музыка ACE-Step + Remotion) → 6 **guardian ‖ publisher (`gemini-3.7-flash-high`)** → фикс-луп ≤ 2 → 7 fixic при инцидентах.
5. Ответ: путь к `aphelia-memory/runs/<slug>/out/<slug>.mp4`, длительность, контакт-лист картинкой, 3 заголовка, стиль-пресет и музыка.

`PLUGIN_ROOT`: текущий workspace, если в нём `scripts/render.py` + `.cursor-plugin/plugin.json`, иначе `%USERPROFILE%\.cursor\plugins\local\aphelia`. Память — `./aphelia-memory/` текущего workspace.

Slug: латиница, дефисы, ≤ 30 символов (`dreamx-creator`). Длительность по умолчанию 75 с (диапазон 60–95).
