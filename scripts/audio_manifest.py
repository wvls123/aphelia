"""Scan templates/audio and write manifest.json with durations (used by compose/Remotion for SFX length)."""

from __future__ import annotations

from pathlib import Path

from common import TEMPLATES, ffprobe_duration, say, write_json


def build() -> dict:
    audio = TEMPLATES / "audio"
    manifest: dict[str, dict[str, float]] = {"sfx": {}, "bgm": {}}
    for kind in ("sfx", "bgm"):
        for f in sorted((audio / kind).glob("*.mp3")):
            manifest[kind][f.stem] = round(ffprobe_duration(f), 3)
    write_json(audio / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    m = build()
    say({"sfx": len(m["sfx"]), "bgm": len(m["bgm"]), "file": str(Path(TEMPLATES / "audio" / "manifest.json"))})
