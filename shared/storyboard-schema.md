# Storyboard v5 — схема (единственный источник правды для рендера Remotion)

Файл: `<run>/storyboard.json`. Пишет агент `framepro-storyboarder`. Проверка: `python scripts/validate_storyboard.py --project <run>` → 0 errors обязательно, warnings — устранить или обосновать во фрагменте. Затем `python scripts/timeline.py --project <run>` создаёт `timeline.json` с абсолютными секундами. Каталог эффектов и когда что применять — `shared/remotion-capabilities.md`, `shared/motion-library.md`.

Холст 1080×1920, 30 fps. Координаты — пиксели холста. Безопасные зоны: сверху ≥180 px (UI платформы), снизу субтитры на `captions.y` (по умолчанию 1560) — не ставить важные объекты в 1480–1700 по y, ниже 1700 — UI платформы.

```json
{
  "id": "slug",
  "lang": "ru",
  "width": 1080, "height": 1920, "fps": 30,
  "script_file": "script.txt",
  "style_preset": "newsroom-orange",
  "style": { "bg": "#FFFFFF", "ink": "#111111", "accent": "#FF7A1A", "danger": "#1B4DFF", "muted": "#6B7280", "font_head": "Inter", "font_hand": "Neucha" },
  "captions": { "y": 1560, "size": 60, "max_sec": 1.1, "style": "box" },
  "bgm": { "src": "audio/bgm-generated.mp3", "vol": 0.35 },
  "scenes": [ ... ]
}
```

- `style_preset` — имя выбранного пресета (см. motion-library); `style.accent`/`danger` под него. Один и тот же акцент два ролика подряд — ошибка вкуса.
- `captions.style`: `box` | `outline` | `karaoke`.
- `bgm.src`: `audio/bgm-generated.mp3` (+ `<run>/music-brief.json`, см. `shared/music-contract.md`) или библиотечный `audio/<name>.mp3`.

## Сцена

```json
{
  "id": "hook",
  "say": "Точный фрагмент сценария, который звучит в этой сцене.",
  "bg": "paper | ink | accent | danger",
  "transition": { "type": "none | push | wipe | fade | flip | clock | iris | zoom | flash | slice", "dir": "left|right|up|down", "sfx": "paper-slide", "sfx_vol": 0.4 },
  "handheld": 0,
  "motion_blur": true,
  "layers": [ ... ],
  "camera": [ { "at": 0, "zoom": 1.0 }, { "at_word": "удар", "zoom": 1.15, "x": 540, "y": 900, "ease": "crash", "shake": 10 } ],
  "sfx": [ { "name": "bass-hit-short", "at_word": "удар", "vol": 0.55 } ]
}
```

- `say` — конкатенация всех `say` **дословно равна** `script.txt`. Одна сцена = 1–2 предложения, ≤ 26 слов (~2–9 с).
- `bg` — палитра сцены. `paper` по умолчанию; `ink` (чёрная — панчи; стикеры автоматически инвертируются); `accent`; `danger`. 1–3 инвертированные сцены на ролик.
- `transition` — первая сцена `none`. `dir` — куда уходит старая сцена. SFX перехода ротируется автоматически, `sfx` задаёт явно.
- `handheld` — дрейф камеры 0–8 px (документальность). `motion_blur` — по умолчанию включается на crash/shake.
- Время: `at` — секунды от начала сцены; `at_word` — слово из `say`. Предпочитай `at_word`.
- `camera`: `zoom` 0.8–1.6, `x`,`y` — точка холста в центре кадра; `ease: smooth|crash`; `shake` 8–14 px на ударах. Видимая область при zoom z: `x ± 540/z`, `y ± 960/z` — валидатор проверяет.

## Слои

Общие поля: `type`, `x`, `y`, `at | at_word`, `color` (`ink|accent|danger|muted` или hex). HUD-слои (не двигаются камерой): `kicker`, `headline`.

| type | обязательные | необязательные | что делает |
|---|---|---|---|
| `kicker` | `text`, `x`, `y` | `size` (44), `color` (muted) | рукописная надпечатка (дата, шаг, рубрика); ≥ 60 px выше заголовка |
| `headline` | `text`, `x`, `y`, `w`, `size` | `hl` (фразы под маркер), `anim`: `rise` (дефолт), `slam`, `words`, `typewriter`, `blur`, `flip`; `lines` (3); `color` | заголовок; `size` — максимум, fitText уменьшит под `w`/`lines` |
| `stamp` | `text`, `x`, `y` | `size` (150), `rot`, `color` | штамп с тряской |
| `label` | `text`, `x`, `y` | `color` (accent/ink) | пилюля |
| `bignum` | `value` ("1 200", "6 $", "0,69"), `x`, `y`, `size` | `deco`: `circle|underline|none`, `deco_color`, `label`, `color` | count-up с единицами/десятичными, обводка рисуется |
| `image` | `src` ("cut/name.png"), `x`, `y`, `w` или `h` | `anim`: `pop`, `spring`, `spin`, `wipe`, `slide` (+`from`), `run` (+`to_x`), `shake`, `swing`, `zoomin`, `drop`; `dur`; `float`; `trail` | стикер-вырезка |
| `arrow` | `from` [x,y], `to` [x,y] | `bend`, `width` (10), `color`, `dur` | рисуемая стрелка |
| `list` | `items` [{`text`, `at_word`?}], `x`, `y`, `w` | `size` (52), `bullet`: `check|dash|num`, `color` | чек-лист по словам |
| `quote` | `text`, `x`, `y`, `w` | `author`, `size` (64), `color` | цитата |
| `bars` | `items` [{`label`, `value`, `color`?, `suffix`?, `at_word`?}], `x`, `y`, `w` | `size` (40), `max`, `color` | столбики с count-up |
| `check` | `x`, `y` | `kind`: `check|cross`, `size` (220), `color` | галочка/крест штрихом |
| `scribble` | `x`, `y`, `w`, `h` | `shape`: `circle|underline`, `color`, `width`, `dur` | обвести/подчеркнуть от руки |
| `shape` | `x`, `y` | `shape`: `burst` (дефолт) `circle|ellipse|star|triangle|pie`, `size` (300), `color`, `anim`: `pop|spin|pulse`, `progress` (pie), `points`, `rot` | геометрия-акцент (взрыв за штампом, доля) |
| `waveform` | `x`, `y` | `src` (vo.mp3), `w` (600), `h` (240), `bars` (24), `color` | эквалайзер, реагирующий на звук |
| `video` | `src` ("videos/name.mp4"), `x`, `y`, `w`, `h` | `rot`, `url`, `seek` | рамка браузера с записью страницы |
| `lottie` | `src` ("lottie/name.json"), `x`, `y` | `w`, `h`, `loop`, `speed` | анимированный стикер (лицензия!) |
| `custom` | `component` (PascalCase), `x`, `y` | `props` | свой компонент `<run>/custom/<Name>.tsx` |

В `say` числа всегда словами; на экране — цифрами.

## SFX

Имена — из `templates/audio/sfx-catalog.json` (186 звуков, теги по смыслу на русском: `удар`, `замок`, `клавиатура`, `часы`, `аплодисменты`, `стекло`, `магия`…). Выбирать по смыслу текста бита. Громкость 0.3–0.6. Один звук ≤ 3 раз на ролик, 0–2 на сцену. Короткие алиасы первой библиотеки (`whoosh`, `impact`, `pop`, `marker`…) тоже работают.
