"""QA a rendered reel: contact sheet + per-scene frames, audio loudness, duration and timeline sanity.

    python scripts/qa.py --project framepro-memory/runs/<slug>

Writes <run>/qa/contact.jpg, <run>/qa/scene-XX-<id>.jpg (+ -late.jpg at 88 %), hook.jpg, last.jpg and <run>/qa-report.json.
The guardian agent then LOOKS at the images (Read tool) and decides PASS / FIX.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from common import ffprobe_duration, read_json, say, sh, write_json


def loudness(path: Path) -> dict:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stderr
    i = re.search(r"I:\s*(-?[\d.]+) LUFS", out.split("Summary:")[-1])
    tp = re.search(r"Peak:\s*(-?[\d.]+) dBFS", out.split("Summary:")[-1])
    return {"integrated_lufs": float(i.group(1)) if i else None, "true_peak_dbfs": float(tp.group(1)) if tp else None}


def grab(video: Path, t: float, dst: Path, width: int = 360) -> None:
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={width}:-1", dst], quiet=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--engine", default="", help="legacy suffix; leave empty")
    args = ap.parse_args()
    project = Path(args.project)
    tl = read_json(project / "timeline.json")
    brief = read_json(project / "brief.json") if (project / "brief.json").exists() else {}
    video = project / "out" / (f"{tl['id']}.{args.engine}.mp4" if args.engine else f"{tl['id']}.mp4")
    if not video.exists():
        raise SystemExit(f"render not found: {video}")
    qa = project / "qa"
    qa.mkdir(exist_ok=True)
    dur = ffprobe_duration(video)

    # one frame per scene (~40% in, after entrances) + hook frame at 0.5s + last frame
    frames: list[Path] = []
    for i, sc in enumerate(tl["scenes"]):
        span = sc["next_start"] - sc["start"]
        t = min(sc["start"] + span * 0.45, dur - 0.1)
        dst = qa / f"scene-{i:02d}-{sc['id']}{args.engine and "-" + args.engine}.jpg"
        grab(video, t, dst, 540)
        frames.append(dst)
        # late frame: layers that appear on the last words + camera at its final key
        grab(video, min(sc["start"] + span * 0.88, dur - 0.1), qa / f"scene-{i:02d}-{sc['id']}-late{args.engine and "-" + args.engine}.jpg", 540)
    grab(video, 0.5, qa / f"hook{args.engine and "-" + args.engine}.jpg", 540)
    grab(video, max(0.0, dur - 0.3), qa / f"last{args.engine and "-" + args.engine}.jpg", 540)

    # contact sheet 4 columns
    small = []
    for i, f in enumerate(frames):
        s = qa / f"_s{i}.jpg"
        grab(video, min(tl["scenes"][i]["start"] + (tl["scenes"][i]["next_start"] - tl["scenes"][i]["start"]) * 0.45, dur - 0.1), s, 270)
        small.append(s)
    cols = 4
    rows = (len(small) + cols - 1) // cols
    inputs: list[str] = []
    for s in small:
        inputs += ["-i", str(s)]
    blank = qa / "_blank.jpg"
    if len(small) % cols:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=270x480", "-frames:v", "1", str(blank)], check=True)
    while len(small) % cols:
        inputs += ["-i", str(blank)]
        small.append(blank)
    n = len(small)
    filt = "".join(f"[{i}:v]" for i in range(n)) + f"xstack=inputs={n}:layout=" + "|".join(f"{(i % cols) * 270}_{(i // cols) * 480}" for i in range(n))
    contact = qa / f"contact{args.engine and "-" + args.engine}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", filt, str(contact)], check=True)
    for s in set(small):
        s.unlink(missing_ok=True)

    loud = loudness(video)
    checks = {
        "duration_ok": brief.get("min_seconds", 60) <= dur <= brief.get("max_seconds", 120) if brief else dur >= 60,
        "loudness_ok": loud["integrated_lufs"] is not None and -16 <= loud["integrated_lufs"] <= -12,
        "peak_ok": loud["true_peak_dbfs"] is not None and loud["true_peak_dbfs"] <= -0.5,
        "scenes": len(tl["scenes"]),
        "avg_scene_sec": round(dur / max(1, len(tl["scenes"])), 2),
        "caption_pages": len(tl["captions"]),
    }
    report = {
        "engine": args.engine,
        "file": str(video),
        "duration": round(dur, 2),
        "loudness": loud,
        "checks": checks,
        "contact_sheet": str(contact),
        "frames": [str(f) for f in frames],
        "hook_frame": str(qa / f"hook{args.engine and "-" + args.engine}.jpg"),
        "last_frame": str(qa / f"last{args.engine and "-" + args.engine}.jpg"),
        "machine_pass": bool(checks["duration_ok"] and checks["loudness_ok"] and checks["peak_ok"]),
    }
    write_json(project / f"qa-report{args.engine and "-" + args.engine}.json", report)
    say({k: report[k] for k in ("duration", "loudness", "checks", "contact_sheet", "machine_pass")})


if __name__ == "__main__":
    main()


