"""Render a run with Remotion: timeline → sync → `remotion render` → loudness-normalised MP4 in <run>/out/.

    python scripts/render.py --project framepro-memory/runs/<slug> [--skip-timeline] [--concurrency 8]

Steps: timeline.py → prepare run assets (SFX/BGM the timeline references) → sync_remotion.py (data.ts,
public/, custom components) → npx remotion render → ffmpeg loudnorm (−14 LUFS, limiter −1 dBTP, faststart).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from common import PLUGIN_ROOT, TEMPLATES, ffprobe_duration, npx_bin, read_json, say, sh

SCRIPTS = Path(__file__).resolve().parent
REMOTION = TEMPLATES / "remotion"


def generate_music(project: Path) -> None:
    """Original bed via ACE-Step (scripts/music.py inside its own uv environment)."""
    ace = Path(os.environ.get("FRAMEPRO_ACE_STEP", PLUGIN_ROOT / "vendor" / "ace-step"))
    if not (ace / "pyproject.toml").exists():
        raise SystemExit(f"ACE-Step not installed at {ace} — run install-plugin.ps1 or set FRAMEPRO_ACE_STEP")
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv not found on PATH (needed for ACE-Step)")
    sh([uv, "run", "--directory", ace, "python", SCRIPTS / "music.py", "--project", project])


def prepare_assets(project: Path) -> None:
    """Copy every SFX file the timeline references; generate or copy the BGM bed."""
    assets = project / "assets"
    tl = read_json(project / "timeline.json")
    (assets / "audio").mkdir(parents=True, exist_ok=True)
    for name in {hit["name"] for hit in tl["sfx"]}:
        shutil.copy2(TEMPLATES / "audio" / "sfx" / f"{name}.mp3", assets / "audio" / f"{name}.mp3")
    if tl.get("bgm"):
        dst = assets / tl["bgm"]["src"]
        if dst.exists():
            return
        if Path(tl["bgm"]["src"]).stem == "bgm-generated":
            generate_music(project)
            if not dst.exists():
                raise SystemExit("music.py finished but assets/audio/bgm-generated.mp3 is missing")
            return
        lib = TEMPLATES / "audio" / "bgm" / Path(tl["bgm"]["src"]).name
        if not lib.exists():
            raise SystemExit(f"bgm not found: {dst} (generate with scripts/music.py or pick a library track)")
        shutil.copy2(lib, dst)


def finalize(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    sh(
        # single-pass loudnorm can overshoot its TP target on transients — a brick-wall limiter at -1 dBTP guarantees it
        ["ffmpeg", "-v", "error", "-y", "-i", src, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9,alimiter=limit=0.891:attack=3:release=40:level=false", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst],
        quiet=True,
    )


def render(project: Path, concurrency: int) -> Path:
    sh([sys.executable, SCRIPTS / "sync_remotion.py", "--project", project])
    out = project / "render-remotion.mp4"
    sh([npx_bin(), "remotion", "render", "Reel", str(out), "--concurrency", str(concurrency)], cwd=REMOTION)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--skip-timeline", action="store_true")
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    project = Path(args.project).resolve()
    if not args.skip_timeline:
        sh([sys.executable, SCRIPTS / "timeline.py", "--project", project])
    prepare_assets(project)
    tl = read_json(project / "timeline.json")
    raw = render(project, args.concurrency)
    dst = project / "out" / f"{tl['id']}.mp4"
    finalize(raw, dst)
    try:
        raw.unlink()
    except OSError:
        pass
    say({"file": str(dst), "duration": round(ffprobe_duration(dst), 2), "scenes": len(tl["scenes"])})


if __name__ == "__main__":
    main()
