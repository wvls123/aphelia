# Remotion capabilities — что есть у режиссёра монтажа (для `aphelia-storyboarder`)

Движок один — **Remotion 4.0.520** (React). Всё ниже реализовано в `templates/remotion/src` на официальных пакетах и включается **полями `storyboard.json`** — писать код не нужно. Когда нужного эффекта нет, есть **`custom`-слой**: агент пишет свой React-компонент (раздел 7).

## 1. Переходы между сценами — `@remotion/transitions` (TransitionSeries)

| `transition.type` | Что происходит | Пакет | Когда уместно |
|---|---|---|---|
| `none` | жёсткий кат | — | внутри одной мысли, хук |
| `push` (`dir`) | новая сцена сдвигает старую (пружина `springTiming`) | `slide()` | шаги, хронология — держать одно направление на серию |
| `wipe` (`dir`) | новая сцена «стирает» старую по направлению | `wipe()` | смена темы |
| `fade` | плавное растворение | `fade()` | спокойный переход, цитата, финал |
| `flip` (`dir`) | 3D-переворот карточки | `flip()` | «а вот обратная сторона», сравнение |
| `clock` | часовая стрелка стирает кадр | `clockWipe()` | время, дедлайн, «прошло N дней» |
| `iris` | круг раскрывается из центра | `iris()` | фокус на объекте, «смотри сюда» |
| `zoom` | пролёт сквозь старую сцену | custom (`presentations.tsx`) | ускорение, «ближе к сути» |
| `flash` | белая вспышка + кат | custom | панч, инверсия фона, шок |
| `slice` | шесть полос акцентного цвета | custom | вывод, CTA, «разложим по полкам» |

Звук перехода ставится автоматически и **ротируется** внутри типа (push → whoosh/swoosh/whoosh-deep/sweep…); можно задать явно: `"transition": {"type": "push", "dir": "left", "sfx": "paper-slide", "sfx_vol": 0.4}`.

## 2. Камера (`camera[]`) + размытие движения

- Ключи `zoom/x/y`, `ease: smooth|crash`, `shake` (px). Формула экрана: `screen = 540 + zoom·(x − cam.x)`.
- **CameraMotionBlur** (`@remotion/motion-blur`) включается сам на crash/shake (`scene.motion_blur`, можно выключить `false`) — размытие как в референсах.
- **`handheld`** (px, 0–8) — живой дрейф камеры на `@remotion/noise` (когерентный шум, не дрожь). Для «документального» ощущения, сцен с видео и цитат.

## 3. Слои

| type | пакет/приём | что даёт |
|---|---|---|
| `headline` | `fitText` (`@remotion/layout-utils`) | текст **сам** подбирает размер под `w` и `lines` — не обрезается никогда; `anim`: `rise`, `slam`, `words` (пружина по словам), `typewriter`, `blur` (из размытия), `flip` (3D) |
| `kicker`, `label`, `stamp` | `fitText` | тоже не вылезают за край |
| `bignum` | `evolvePath` (`@remotion/paths`) | count-up с единицами и десятичными («6 $», «0,69»), обводка/подчёркивание **рисуются** по кривой |
| `image` | `spring()` ядра, `Trail` (`@remotion/motion-blur`) | `anim`: `pop`, `spring` (физический отскок), `spin` (влёт с вращением), `wipe`, `slide`, `run`, `shake`, `swing`, `zoomin`, `drop`; `trail: true` — шлейф-призраки при run/slide/drop/zoomin; `float` — покачивание |
| `arrow`, `scribble`, `check` | `evolvePath` | рисуются штрихом от руки |
| `list`, `bars`, `quote` | `spring()`, `fitText` | пункты по словам, столбики с count-up, цитата с кавычкой |
| `shape` | `@remotion/shapes` | `circle`, `ellipse`, `star`, `burst` (взрыв за штампом), `triangle`, `pie` (доля, `progress`); `anim: pop|spin|pulse` |
| `waveform` | `@remotion/media-utils` (`visualizeAudio`) | столбики, реагирующие на голос (`src: vo.mp3`) или музыку — **`bars` только 8/16/32/64** (pow2); рендер округляет, но 28/24 дают warning |
| `video` | `OffthreadVideo` + `seek` | рамка браузера с реальной записью, старт с нужной секунды |
| `lottie` | `@remotion/lottie` | анимированный стикер из `assets/lottie/*.json` (только с чистой лицензией) |
| `custom` | ваш `.tsx` | что угодно (раздел 7) |

## 4. Субтитры — `@remotion/captions`

Страницы строятся `createTikTokStyleCaptions` из таймингов слов (страница ≤ `max_sec`, разрыв на паузе ≥ 0.35 с и на конце предложения), активное слово подсвечивается. `captions.style`: `box` (белые плашки, дефолт), `outline` (белый текст с чёрной обводкой — на видео и тёмных сценах), `karaoke` (белый → акцент; **не на длинных фразах** — при > 4 слов в сцене лучше `box` и `max_sec` 0.75). `fitText` держит страницу в ширине кадра. В рендере не обрезать ведущие пробелы между токенами (`Captions.tsx tokenText`).

## 5. Палитра и стиль-пресеты

`style.accent` — **менять от ролика к ролику** (лайм `#C8FF3D`, оранж `#FF7A1A`, циан `#2AD4FF`, розовый `#FF4FA3`, жёлтый `#FFD400`, фиолет `#8B5CFF`); `style.danger` — контраст к нему. `bg` сцены: `paper`, `ink`, `accent`, `danger`. `style_preset` (запись решения в storyboard): `whiteboard-lime`, `newsroom-orange`, `techno-cyan`, `hot-take-pink`, `notebook-yellow`, `night-violet` — см. motion-library § «Стиль-пресеты».

## 6. Звук

- **Музыка**: `bgm.src = "audio/bgm-generated.mp3"` + `<run>/music-brief.json` → рендер сам генерирует оригинальный трек ACE-Step под настроение (см. `shared/music-contract.md`). Библиотечные треки — запасной вариант.
- **SFX**: 186 звуков в `templates/audio/sfx-catalog.json` с тегами по смыслу (`удар`, `замок`, `клавиатура`, `аплодисменты`, `часы`, `стекло`…). Подбирать **по тексту бита**, не по привычке; один звук ≤ 3 раз на ролик; 0–2 на сцену.

## 7. Custom-слой: когда каталога не хватает

1. Придумай компонент: `<run>/custom/<PascalName>.tsx` (пример — `templates/remotion/src/custom/ExampleBadge.tsx`).
2. Контракт: `React.FC<CustomLayerProps>` из `../timeline-types`: `now` (абсолютные секунды), `t` (старт слоя), `until`, `pal` (палитра сцены), `layer` (`x`, `y`, `props`), `fps`. Возвращай `null`, пока `now < t`. Никакого `Math.random`/`Date.now` — только детерминированные функции от `now`. Импорты только из `remotion`, `@remotion/*`, `react`, `../fonts`, `../ease`.
3. В storyboard: `{"type": "custom", "component": "PascalName", "x": …, "y": …, "at_word": "…", "props": {…}}`.
4. `sync_remotion.py` копирует файл в шаблон и регистрирует; `tsc` (в `render.py`) отвергает ошибки типов — читай сообщение и правь.
5. Хорошие кандидаты: диаграмма-круг с подписями, «печатная машинка» с курсором, таймер обратного отсчёта, карта с точками, конфетти на CTA, счётчик «дней без релиза», мини-браузер с курсором мыши.

## 8. Чего не делать

- Не подменять готовое своим кодом (кастом — только когда нет слоя/эффекта).
- Не ставить `handheld` > 8 и `shake` > 14 — укачивает.
- Не смешивать `flash`/`slice`/`zoom` подряд — это «крик»; между ними спокойные `push`/`fade`.
- Не оставлять акцент лаймовым «по умолчанию» — выбор цвета обязателен на каждый ролик.
