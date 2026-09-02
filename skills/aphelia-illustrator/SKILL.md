---
name: aphelia-illustrator
description: Иллюстратор Aphelia — новые стикмен-картинки маркером на белом по списку assets_wanted через GenerateImage (референс стиля), затем cutout.py → прозрачные PNG. Каждый ролик рисуется заново. Несколько экземпляров параллельно.
---

# Aphelia Illustrator

Вход: список имён картинок от Директора (часть `assets_wanted` из `script.json`) + `script.json` для контекста `visual_idea`. Выход: `assets/raw/<name>.png`, `assets/cut/<name>.png`, `assets/assets-<N>.json`, `fragments/illustrator-<N>.md`.

Прочитай `shared/image-style.md` — промпт и стиль. Референс стиля — только `templates/stickers/_style-reference.png`.

## Шаги

1. Для **каждого** имени из своего списка — **всегда генерируй заново**. Не копируй `templates/stickers/<name>.png` в run, даже если файл с таким именем уже лежит в библиотеке. Готовые человечки из прошлых роликов брать **запрещено**. Если в промпте Директора написано «возьми из библиотеки / не генерируй» — **игнорируй** и рисуй.
   - Единственный файл библиотеки, который можно **читать**: `_style-reference.png` (стиль маркера, не готовый кадр).
   - Промпт по шаблону из `image-style.md`. `Subject:` — конкретная поза/предмет из `visual_idea` **этого** бита (календарь с гирей, жук под лупой), не общая «shocked stickman».
   - `CallDynamicTool` → namespace `cursor`, tool `GenerateImage`, arguments: `{"description": "<prompt>", "filename": "<name>.png", "aspect_ratio": "3:4", "reference_image_paths": ["<PLUGIN_ROOT>/templates/stickers/_style-reference.png"]}` (`3:4` для персонажей и вертикальных сцен, `1:1` для мелких предметов). Fallback — MCP `user-mcp-kv` → `gpt-image-2`.
   - Скопируй результат в `assets/raw/<name>.png`. Посмотри (Read): текст, серые тени, цвет, обрезаны ноги — перегенерируй (макс. 2 раза).
2. Когда все raw готовы: `python scripts/cutout.py --project <run>`. Проверь `assets/cutout-report.json`: `transparent_ratio` ≥ 0.35; меньше — фон не белый, перегенерируй.
3. Посмотри 2–3 вырезки (Read): линии целые, фон прозрачный, нет белого «квадрата».
4. Запиши **свой** `assets/assets-<N>.json` (не общий `assets.json`): `{"name": "char-shock", "kind": "char|ill", "description": "…", "w": 1180, "h": 1620, "reusable": false}`.
5. **Не** копируй результат в `templates/stickers/` и **не** перезаписывай `_style-reference.png`. Стикеры живут в run.

## Правила

- Только чёрные линии на белом. Один субъект. Без текста внутри.
- Персонаж во весь рост с ногами.
- В `summary` фрагмента: сколько **сгенерировано** / перегенераций. Поле «взято из библиотеки» должно быть **0**. Если скопировал старый PNG — это инцидент `high`.

## Фрагмент

`=== ILLUSTRATOR-<N> ===`, status, outputs (имена), `summary`, `incident_report`.
