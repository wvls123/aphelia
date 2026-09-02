---
name: aphelia-voice
description: Спроектировать или обновить фирменный голос диктора Aphelia (Qwen3-TTS VoiceDesign → референс для клона)
---

# /aphelia-voice [--name narrator-ru] [--instruct "описание голоса"]

Директор запускает сам (инфраструктура, не творчество):

```powershell
python scripts/voice.py design-voice --name <name> [--instruct "..."] [--tries 6]
```

Результат: `voices/<name>/ref.wav`, `ref.txt` (с ударениями), `meta.json` (дубли, выбранный, темп). Затем можно прослушать `ref.wav` и, если голос не нравится, повторить с другим `--instruct` (описание на английском: пол, возраст, тембр, темп, характер). Все следующие ролики клонируют этот голос — см. `shared/voice-contract.md`.

Проверка на реальном тексте: `python scripts/voice.py narrate --project <run> --limit 3` (первые 3 предложения).
