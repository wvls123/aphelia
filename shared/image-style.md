# Стиль генерируемых изображений (по референсу пользователя)

Референс — чёрно-белый **стикмен маркером** на чистом белом фоне: круглая голова, точки-глаза, простое тело, галстук, толстые неровные линии от руки. Картинки идут в ролик **вырезками** (прозрачный PNG через `pipeline/cutout.py`), а не квадратами.

## Базовый промпт (EN, для генератора)

```
Black-and-white cartoon stick figure, hand-drawn marker doodle style,
thick uneven black ink lines, pure white background, no shading, no gray,
no color. Simple round head with dot eyes and expressive mouth, thin body,
small necktie. Whiteboard explainer look. No text, no letters, no logos.
Full body in frame, generous white margins.
Subject: <SUBJECT>.
```

Для сцен-иллюстраций (клетка, стена, календарь, серверная стойка) — тот же промпт, но `Subject` описывает объект + стикменов вокруг него.

## Правила

- Только чёрные линии на белом. Цвет (лайм `#C8FF3D`, красный `#FF3B30`) добавляет движок: маркер-подсветка, штампы, стрелки.
- Без текста внутри картинки — текст кладёт движок (иначе он не совпадёт с озвучкой).
- Один субъект / одна понятная сцена на картинку.
- После генерации: `python scripts/cutout.py --project <run>` → все `assets/raw/*.png` становятся `assets/cut/*.png` с альфой (rembg + маска по чернилам, чтобы не терять тонкие линии). Отчёт `assets/cutout-report.json` — `transparent_ratio` должен быть ≥ 0.35, иначе картинка не вырезалась (серый фон, тени) — перегенерировать.
- Сырые картинки лежат в `<run>/assets/raw/`, готовые вырезки — в `<run>/assets/cut/`. В storyboard всегда `cut/<name>.png`.
- Генерация: инструмент `GenerateImage` (namespace `cursor`) **на каждый ролик заново**, с `reference_image_paths` на `templates/stickers/_style-reference.png`. Fallback — MCP `user-mcp-kv` → `gpt-image-2`. Файл результата копировать в `assets/raw/<name>.png`.
- **Не** подставлять готовые PNG из `templates/stickers/` (кроме `_style-reference.png` как референса стиля). Одинаковое имя (`char-shock`) ≠ тот же рисунок: в этом run картинка новая.

## Именование

- `char-<эмоция|поза>` — стикмен: `shock, point, think, shrug, celebrate, run, facepalm, idea, stop, whisper, sleep, angry, wave`.
- `ill-<предмет>` — предмет или мини-сцена: `sandbox, wall, rack, cage, calendar, megaphone, lock, cloud, chart, shield, bug, key, phone, laptop`.
- Имена — схема для сториборда, не склад. Subject в промпте берётся из `visual_idea` **этой** новости.

## Набор текущего ролика

| Файл | Subject |
|---|---|
| `char-shock` | stick figure, hands on head, shocked open mouth |
| `char-point` | stick figure pointing to the left with a big smile |
| `char-think` | stick figure with hand on chin and a question mark above |
| `char-shrug` | stick figure shrugging with palms up, doubtful face |
| `char-celebrate` | stick figure jumping with arms up, big grin |
| `char-run` | stick figure sprinting, motion lines behind |
| `ill-sandbox` | a sandbox with five stick figures around a pin board with notes |
| `ill-wall` | brick wall with a hole, one stick figure climbing through, crowd behind |
| `ill-rack` | open server rack cabinet, stick figure inside pulling cables |
| `ill-cage` | stick figure inside a birdcage with a padlock, thumbs up |
| `ill-calendar` | wall calendar with crossed-out days, stick figure asleep in an armchair |
| `ill-megaphone` | stick figure shouting into a megaphone |
