# Ресёрч стека

## Что реально сделало референсы

Оба MP4 помечены **Remotion 4.0.506**: React-компоненты → headless Chromium по кадрам → FFmpeg. Это не HyperFrames-рендер, но тот же класс пайплайна (DOM → MP4).

## Два движка

| | [Remotion](https://github.com/remotion-dev/remotion) | [HyperFrames](https://github.com/heygen-com/hyperframes) |
|---|---|---|
| Авторство | React / TSX, `useCurrentFrame`, `interpolate` | HTML + CSS + GSAP, `data-start` / `data-duration` |
| Для агента | skills `npx remotion skills add` | skills `/hyperframes`, CLI без TTY |
| Сборка | webpack/bundler | `index.html` как есть |
| Лицензия | Remotion License (платно от 4 сотрудников) | Apache 2.0 |
| Облако | Remotion Lambda | local / HeyGen cloud / AWS Lambda |

Выбор для этого репозитория: **HyperFrames как рендерер** (агент пишет HTML, нет коммерческого порога, skills уже стоят). Визуальный язык копируем с Remotion-референса, не исходники React.

Официальный порт: skill `/remotion-to-hyperframes`. Сравнение: [HyperFrames vs Remotion](https://hyperframes.heygen.com/guides/hyperframes-vs-remotion).

## Смежные репозитории (конвейер «тема → ролик»)

- [SucksToBeAnik/OpenReels](https://github.com/SucksToBeAnik/OpenReels) — research → script → TTS → картинки → captions → Remotion 9:16.
- [AirKyzzZ/content-engine](https://github.com/AirKyzzZ/content-engine) — Claude script + Edge TTS + Remotion.
- [jaebong-human/shorts-gen](https://github.com/jaebong-human/shorts-gen) — GPT + DALL·E + TTS + Remotion.
- [sanky369/yt-hyperframes-agent](https://github.com/sanky369/yt-hyperframes-agent) — talking-head → HyperFrames overlays.
- [Khizergenfox/ai-shorts-pipeline](https://github.com/Khizergenfox/ai-shorts-pipeline) — Remotion + ElevenLabs + Veo.
- [floomhq/opencut](https://github.com/buildingopen/opencut) — TypeScript timeline + Whisper + Remotion.

Локально для русской речи: **edge-tts** (`ru-RU-DmitryNeural`). `hyperframes tts` = Kokoro, без русского.

## Готовые вещи Remotion (не пишем с нуля)

Официальные пакеты (ставятся рядом с `remotion`, версии синхронизированы):

| Пакет | Что даёт |
|---|---|
| `@remotion/transitions` | `TransitionSeries` + готовые переходы: `wipe()`, `slide()`, `fade()`, `flip()`, `clockWipe()` |
| `@remotion/captions` | TikTok-стиль субтитры, `createTikTokStyleCaptions`, подсветка активного слова |
| `@remotion/google-fonts` | Загрузка шрифтов (включая кириллицу Inter) без ручных `@font-face` |
| `@remotion/shapes` | SVG-фигуры: круги, стрелы, звёзды, многоугольники |
| `@remotion/animation-utils` | `spring`, `interpolate`, `Easing`, `measureSpring` |
| `@remotion/lottie` | Lottie-анимации из After Effects |
| `@remotion/three` | Three.js 3D-сцены внутри композиции |
| `@remotion/media-utils` | `getAudioDuration`, `getVideoMetadata`, визуализация waveform |
| `@remotion/player` | Веб-плеер для превью ролика на сайте |
| Remotion Lambda / Cloud Run | Серверless-рендер в облаке |
| `npx remotion skills add` | Agent Skills — правила для Claude Code / Cursor |
| `npx create-video` | Готовые шаблоны (blank, hello-world, next, tailwind…) |

Сообщество:

- [neutral-Stage/remotion-captioneer](https://github.com/neutral-Stage/remotion-captioneer) — 14 стилей караоке-субтитров, 6 STT-провайдеров.
- [vshukla7/remotion-captions-themes](https://github.com/vshukla7/remotion-captions-themes) — темы kinetic-01, karaoke, beast.
- [seblavoie/remotion-kit](https://github.com/seblavoie/remotion-kit) — `AnimatedText`, пресеты fade/slide/scale.
- [ahgsql/remotion-subtitles](https://github.com/ahgsql/remotion-subtitles) — 17 шаблонов субтитров из SRT.

В нашем `remotion-reel` используем: `@remotion/transitions` (wipe между сценами), `@remotion/google-fonts` (Inter cyrillic), `spring`/`interpolate` из ядра.

## video-shotcraft (Vincentwei1021)

Клонирован в `_templates/shotcraft`: 157 карт рецептов (`references/shots/`: camera, transition, typography, ui-entrance…), библиотека SFX (whoosh/impact/riser/shutter), BGM (Mixkit), проверенный Remotion-шаблон. Ключевые перенятые приёмы:

- звук — актив уровня таймлайна: BGM-бед + SFX, прибитые к кадрам сцен (`sound-design.md`)
- быстрые push-переходы; crash-zoom-punch — не более 2 раз за ролик
- wipe без световой кромки читается как «PPT-переход» — нужна кромка/движение
- реальные скриншоты/скринкасты страниц вместо нарисованного UI

## Пайплайн Framepro (v3)

```
storyboard.json (8 сцен, hero/shot/checklist/stats/split/video/statement/hero_cta)
  → edge-tts (ru-RU-DmitryNeural) + word timings
  → assets: img/ (монохромный 3D, docs/image-style-prompt.md), shots/ (Playwright),
    videos/ (скринкаст Habr, -g 30 для seek), audio/ (SFX shotcraft + BGM bed)
  → HyperFrames (compose.py) + Remotion (sync_remotion.py → src/data.ts)
  → output.mp4 / reel.mp4 1080×1920, со звуковым дизайном
```

Проверено: переходы 0.3 с с пиком движения 25–70 (как референс), −15.5/−17.7 LUFS, видео-вставка играет, кадры сверены.

```
новостной бриф JSON
  → текст сцен (storyboard.json)
  → edge-tts + word timestamps
  → compose.py → index.html (GSAP)
  → hyperframes lint/check
  → hyperframes render → MP4 9:16
```

Скриншоты и B-roll можно добавить следующей волной (`hyperframes capture`). Первая поставка — motion graphics как v5 без PiP.
