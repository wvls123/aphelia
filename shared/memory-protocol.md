# Memory protocol — общая память Framepro

## Корень

`<workspace>/framepro-memory/` (переопределяется `FRAMEPRO_MEMORY`). Каждый ролик — `runs/<slug>/`:

```text
runs/<slug>/
  brief.json            ← init_run.py: тема, источники, длительность, движок, CTA
  00-brief.md
  research.md           ← researcher: фактура, хронология, цитаты, углы
  facts.json            ← researcher: [{fact, number, source, quote}]
  script.json           ← writer: биты (say, purpose, visual_idea, assets_wanted, punch_word)
  script.txt            ← script_check.py --from-json (из беатов)
  stress-overrides.json ← writer (опционально)
  script-check.json
  assets/
    raw/<name>.png      ← illustrator: сгенерированные картинки (белый фон)
    cut/<name>.png      ← cutout.py: прозрачные стикеры
    cutout-report.json
    assets.json         ← illustrator: [{name, kind: char|ill, description, w, h}]
    videos/<name>.mp4   ← screencaster
    vo.mp3 vo.wav vo-words.json vo-duration.txt ← voice
    audio/ fonts/       ← render.py копирует из templates
  voice-report.json     ← voice: дубли, сходство, ударения под сомнением
  storyboard.json       ← storyboarder
  storyboard-validation.json
  timeline.json         ← timeline.py
  music-brief.json      ← storyboarder: caption/bpm для ACE-Step
  music-report.json     ← music.py (seed, модель, лицензия)
  custom/<Name>.tsx     ← storyboarder: свои Remotion-компоненты (слой custom)
  out/<slug>.mp4        ← render.py (готово к загрузке)
  qa/                   ← qa.py: contact.jpg, scene-XX-*.jpg, *-late.jpg, hook.jpg, last.jpg
  qa-report.json, qa-report.md ← guardian
  publish.md            ← publisher: заголовки, описание, хештеги, обложка
  fragments/<role>.md   ← каждый агент пишет только свой фрагмент
  pipeline-fix-queue.md ← инциденты (status: open) для fixic
```

## Handoff

`.cursor/framepro-handoff.md` — только Директор. Сброс через Write одной строкой `# Framepro — новая сессия`. Параллельные агенты одной волны **не** пишут в handoff — только `fragments/<role>.md`; Директор переносит.

## Фрагмент агента (обязательный формат)

```md
=== ROLE (НАЗВАНИЕ) ===
status: ✅ | ⚠️ | ❌
inputs: что читал
outputs: файлы, которые создал (пути)
summary: 3–8 строк по делу
decisions: ключевые решения (эффекты, голос, структура) — коротко, чтобы следующий агент понимал почему
incident_report:
  - none
  # или
  - severity: low|medium|high
    what: что пошло не так
    workaround: что сделал
    durable_fix: что поправить в плагине (skills/scripts/shared)
```

Инциденты со `severity: medium|high` дублируются в `pipeline-fix-queue.md` со `status: open`.

## Контракт решений

Смысловые решения (текст, эффекты, выбор кадров, вердикт QA) принимает **агент** и записывает в JSON сам. Скрипты — только проверяют, считают, рендерят. Скрипт не «придумывает» сторибоард; валидатор не «исправляет» его.
