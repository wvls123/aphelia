"""Capture a scrolling web page into <run>/assets/videos/<name>.mp4 (browser-frame insert).

    python scripts/capture_web.py --project <run> --url https://... --name habr [--seconds 8]

Playwright records .webm; we transcode to H.264 mp4 (30 fps, faststart) so both renderers seek it precisely.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from common import ffprobe_duration, say, sh

NODE_DIR = Path(__file__).resolve().parent / "node"


def capture(project: Path, url: str, name: str, seconds: float) -> Path:
    out_dir = project / "assets" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not (NODE_DIR / "node_modules" / "playwright").exists():
        sh(["npm", "install", "--silent"], cwd=NODE_DIR)
        sh(["npx", "playwright", "install", "chromium"], cwd=NODE_DIR)
    res = subprocess.run(
        ["node", str(NODE_DIR / "record_scroll.mjs"), url, str(out_dir), str(seconds)],
        capture_output=True,
        text=True,
        check=True,
        shell=True,
    )
    info = json.loads(res.stdout.strip().splitlines()[-1])
    webm = Path(info["file"])
    mp4 = out_dir / f"{name}.mp4"
    # Playwright records from context creation (blank page, load, banner click); keep ~0.8 s of the
    # loaded page before the scroll starts and cap the clip at `seconds` + 1.2 s.
    start = max(0.0, info.get("scrollStartMs", 0) / 1000 - 0.8)
    length = min(seconds + 1.2, 10.5)
    sh(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", webm, "-t", f"{length:.2f}", "-an", "-r", "30", "-g", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", mp4],
        quiet=True,
    )
    webm.unlink(missing_ok=True)
    return mp4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--seconds", type=float, default=8)
    args = ap.parse_args()
    mp4 = capture(Path(args.project), args.url, args.name, args.seconds)
    say({"file": str(mp4), "rel": f"videos/{mp4.name}", "duration": round(ffprobe_duration(mp4), 2)})
