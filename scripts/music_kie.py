"""Music adapter: kie.ai Suno (custom mode, instrumental) in place of ACE-Step (needs GPU
we don't have). Reuses music.py's master() unchanged — only generate() is swapped, so the
music-brief.json -> bgm-generated.mp3 contract stays identical for the rest of the pipeline.

Input:  <run>/music-brief.json {"caption": "...", "bpm": 118, "duration": 78,
         "candidates": 2, "seed": null}  (same file aphelia-storyboarder already writes)
Output: <run>/assets/audio/bgm-generated.mp3 (bed level -18 LUFS, fades, exact duration)
        + <run>/music-report.json

Suno's callBackUrl is a required field but does not need to be reachable — kie.ai still
returns the result via polling (velsvisual --wait). Suno tracks render at their own length
(commonly 3-4 min); music.py's master() trims/fades to the exact brief duration, so this is
not a gap, just a note for anyone reading the raw output before mastering.

Usage:
    python scripts/music_kie.py --project aphelia-memory/runs/<slug> [--pick 0]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_json, run_dir, write_json  # noqa: E402
from music import DEFAULT_BRIEF, master  # noqa: E402  (reuse mastering chain as-is)

MODEL = "V4_5"


def generate(brief: dict, out_dir: Path) -> dict:
    caption = brief["caption"][:900]
    style = brief.get("style") or caption
    title = (brief.get("name") or "aphelia-bed")[:80]
    candidates = int(brief.get("candidates", 2))

    with tempfile.TemporaryDirectory() as td:
        cmd = [
            "velsvisual", "run", "suno",
            "--set", f"prompt={caption}",
            "--set", f"model={MODEL}",
            "--set", "customMode=true",
            "--set", f"style={style}",
            "--set", f"title={title}",
            "--set", "instrumental=true",
            "--set", "callBackUrl=https://example.com/aphelia-callback",
            "--wait", "--timeout", "240", "--download", td, "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"kie Suno failed: {result.stdout}\n{result.stderr}")
        tracks = sorted(Path(td).glob("*.mp3"))
        if not tracks:
            raise SystemExit(f"kie Suno: no tracks downloaded. stdout={result.stdout}")
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for i, t in enumerate(tracks[:max(candidates, 1)]):
            dst = out_dir / f"bgm-candidate-{i}.mp3"
            shutil.move(str(t), str(dst))  # cross-device safe (tmp and run dir may be on different mounts)
            saved.append({"path": str(dst)})
        return {"audios": saved}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--caption")
    ap.add_argument("--bpm", type=int)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--candidates", type=int)
    ap.add_argument("--pick", type=int, default=0)
    ap.add_argument("--name", default="bgm-generated")
    args = ap.parse_args()

    project = Path(args.project)
    if not project.exists():
        project = run_dir(args.project)

    brief = dict(DEFAULT_BRIEF)
    brief_path = project / "music-brief.json"
    if brief_path.exists():
        brief.update(read_json(brief_path))
    for k in ("caption", "bpm", "duration", "candidates"):
        v = getattr(args, k)
        if v is not None:
            brief[k] = v

    raw_dir = project / "assets" / "audio" / "_raw"
    result = generate(brief, raw_dir)
    picked = result["audios"][min(args.pick, len(result["audios"]) - 1)]

    out = project / "assets" / "audio" / f"{args.name}.mp3"
    duration = master(Path(picked["path"]), out, float(brief["duration"]))

    report = {"engine": "kie.ai/suno", "brief": brief, "picked": picked["path"], "out": str(out), "duration": round(duration, 2)}
    write_json(project / "music-report.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
