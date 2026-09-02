"""Create a run directory: aphelia-memory/runs/<slug>/ with brief, folders and fragment files.

    python scripts/init_run.py --slug hf-agents-breach --topic "..." [--source URL ...] [--duration 75]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from common import memory_root, say, write_json

FOLDERS = ["assets/raw", "assets/cut", "assets/videos", "assets/audio", "fragments", "out", "qa"]


def init(slug: str, topic: str, sources: list[str], duration: int, engine: str, audience: str, cta: str) -> Path:
    run = memory_root() / "runs" / slug
    for f in FOLDERS:
        (run / f).mkdir(parents=True, exist_ok=True)
    brief = {
        "slug": slug,
        "created": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "sources": sources,
        "target_seconds": duration,
        "min_seconds": max(60, duration - 15),
        "max_seconds": duration + 20,
        "engine": engine,
        "audience": audience,
        "cta": cta,
        "language": "ru",
        "voice": "narrator-ru",
        "style": "whiteboard-stickman",
        "status": "NEW",
    }
    write_json(run / "brief.json", brief)
    (run / "00-brief.md").write_text(
        "# Aphelia — brief\n\n"
        f"- slug: `{slug}`\n- тема: {topic}\n- источники: {', '.join(sources) or '—'}\n"
        f"- длительность: {brief['min_seconds']}–{brief['max_seconds']} с (цель {duration})\n"
        f"- движок: {engine}\n- аудитория: {audience}\n- CTA: {cta}\n- голос: narrator-ru (Qwen3-TTS clone)\n- стиль: белая доска, стикмен-вырезки\n",
        encoding="utf-8",
    )
    (run / "pipeline-fix-queue.md").write_text("# Pipeline fix queue\n\n(агенты добавляют инциденты со `status: open`)\n", encoding="utf-8")
    return run


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--duration", type=int, default=75)
    ap.add_argument("--audience", default="предприниматели, маркетологи, айтишники, которым нужна польза за минуту")
    ap.add_argument("--cta", default="подпишись — разбираю такие кейсы")
    args = ap.parse_args()
    run = init(args.slug, args.topic, args.source, args.duration, "remotion", args.audience, args.cta)
    say({"run": str(run), "brief": str(run / "brief.json")})

