# Music contract — фон под каждый ролик, безопасный для монетизации

## Правило №1: музыка не должна приносить страйки

Единственный надёжный способ — **оригинальный трек на каждый ролик**, сгенерированный локально:

- Модель: **ACE-Step 1.5** (`vendor/ace-step`, лицензия MIT). По карточке модели обучена на лицензированных, royalty-free и синтетических данных; авторы прямо разрешают коммерческое использование сгенерированного. Уникальный трек не совпадёт ни с чем в Content ID.
- Запуск: `render.py` сам вызывает `scripts/music.py`, если в storyboard `bgm.src = "audio/bgm-generated.mp3"` и файла ещё нет. Вручную: `uv run --directory vendor/ace-step python scripts/music.py --project <run>`.
- Вход: `<run>/music-brief.json` от сторибордера:

```json
{
  "caption": "minimal tech house bed for a fast explainer reel, tight punchy drums, deep sub bass, airy synth stabs, no vocals, no hooks that fight speech, steady energy, instrumental",
  "bpm": 122,
  "duration": 78,
  "candidates": 2,
  "seed": null
}
```

- `caption` — по-английски, 1–2 предложения: жанр, настроение, темп, инструменты, **всегда** «no vocals, instrumental, bed for voice-over». Жанр подбирается под ролик (см. таблицу), а не один и тот же.
- `duration` — озвучка + 3 с (скрипт подставит сам из `vo-duration.txt`).
- Выход: `assets/audio/bgm-generated.mp3` (−18 LUFS, фейды, точная длина) + `music-report.json` (caption, seed, модель). В `publish.md` publisher указывает «музыка сгенерирована ACE-Step».

## Настроение → жанр (менять от ролика к ролику)

| Настроение ролика | caption-основа | bpm |
|---|---|---|
| техно-новость, релиз, цифры | minimal tech house / glitchy electronica, tight drums, sub bass | 118–126 |
| расследование, риск, скандал | dark cinematic pulse, low strings, ticking percussion, tension | 90–105 |
| разбор кейса, «как это работает» | lo-fi hip hop, warm keys, soft drums | 82–92 |
| мотивация, вывод, «что делать» | uplifting indie pop / synthwave, bright pads, driving beat | 110–120 |
| ирония, провал, «скачать нечего» | quirky pizzicato, marimba, playful percussion | 100–115 |
| финтех, деньги, экономика | boom-bap / trap-lite, punchy 808, sparse | 86–96 |

## Запасной вариант (библиотека)

`templates/audio/bgm/*.mp3` — Mixkit Stock Music Free License (коммерческое использование без атрибуции). Использовать, только если генерация недоступна (нет GPU/uv). Не грузить один и тот же трек два ролика подряд.

## Громкость

Голос доминирует: `bgm.vol` 0.25–0.45 (бед уже на −18 LUFS). SFX 0.3–0.6. Финальный мастер −14 LUFS / −1 dBTP делает `render.py`.
