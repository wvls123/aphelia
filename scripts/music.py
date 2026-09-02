"""Original background music per reel with ACE-Step 1.5 (MIT, trained on licensed/royalty-free data →
generated tracks are yours to monetise; every reel gets a unique bed, so no Content ID matches).

Runs inside the ACE-Step environment:

    uv run --directory <PLUGIN_ROOT>/vendor/ace-step python <PLUGIN_ROOT>/scripts/music.py --project <run>

Input:  <run>/music-brief.json  {"caption": "...", "bpm": 118, "duration": 78, "candidates": 2, "seed": null}
        (written by framepro-storyboarder after analysing the script's mood; CLI flags override)
Output: <run>/assets/audio/bgm-generated.mp3 (bed level −18 LUFS, fades) + <run>/music-report.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ACE_ROOT = Path(os.environ.get("FRAMEPRO_ACE_STEP", PLUGIN_ROOT / "vendor" / "ace-step"))
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from common import ffprobe_duration, read_json, say, write_json  # noqa: E402

DEFAULT_BRIEF = {
    "caption": "modern minimal tech house bed for a fast-paced explainer reel, clean punchy drums, deep sub bass, "
    "airy synth stabs, no vocals, no melody hooks that fight speech, steady energy, instrumental",
    "bpm": 120,
    "duration": 80,
    "candidates": 2,
    "seed": None,
    "config": "acestep-v15-turbo",
}


def generate(brief: dict, out_dir: Path) -> dict:
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    handler = AceStepHandler()
    # 16 GB class GPU: 2B turbo DiT without LM (caption drives everything), offload keeps headroom for the VAE
    handler.initialize_service(project_root=str(ACE_ROOT), config_path=brief.get("config", "acestep-v15-turbo"), device="cuda", offload_to_cpu=True)
    params = GenerationParams(
        caption=brief["caption"][:512],
        lyrics="[Instrumental]",
        instrumental=True,
        bpm=int(brief["bpm"]) if brief.get("bpm") else None,
        duration=float(brief["duration"]),
        thinking=False,
        use_cot_caption=False,
    )
    seeds = [int(brief["seed"])] if brief.get("seed") is not None else None
    config = GenerationConfig(batch_size=int(brief.get("candidates", 2)), audio_format="wav", seeds=seeds)
    result = generate_music(handler, None, params, config, save_dir=str(out_dir))
    if not result.success:
        raise SystemExit(f"ACE-Step failed: {result.error}")
    return {"audios": [{"path": a["path"], "seed": a.get("params", {}).get("seed"), "key": a.get("key")} for a in result.audios]}


def master(src: Path, dst: Path, duration: float) -> float:
    """Bed level: −18 LUFS, gentle fades, exact length."""
    chain = f"atrim=0:{duration:.2f},afade=t=in:st=0:d=0.6,afade=t=out:st={max(0.0, duration - 1.8):.2f}:d=1.8,loudnorm=I=-18:TP=-2:LRA=7"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", chain, "-ar", "48000", "-b:a", "192k", str(dst)], check=True)
    return ffprobe_duration(dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--caption")
    ap.add_argument("--bpm", type=int)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--candidates", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--pick", type=int, default=0, help="which candidate to master (0-based)")
    ap.add_argument("--name", default="bgm-generated")
    args = ap.parse_args()
    project = Path(args.project)
    brief = dict(DEFAULT_BRIEF)
    if (project / "music-brief.json").exists():
        brief.update(read_json(project / "music-brief.json"))
    for key in ("caption", "bpm", "duration", "candidates", "seed"):
        if getattr(args, key) is not None:
            brief[key] = getattr(args, key)
    vo_dur = project / "assets" / "vo-duration.txt"
    if not args.duration and vo_dur.exists():
        brief["duration"] = round(float(vo_dur.read_text(encoding="utf-8")) + 3.0, 1)
    brief["duration"] = max(10.0, min(600.0, float(brief["duration"])))

    raw_dir = project / "assets" / "audio" / "_music-candidates"
    raw_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    gen = generate(brief, raw_dir)
    pick = gen["audios"][min(args.pick, len(gen["audios"]) - 1)]
    dst = project / "assets" / "audio" / f"{args.name}.mp3"
    dur = master(Path(pick["path"]), dst, brief["duration"])
    report = {
        "file": str(dst),
        "duration": round(dur, 2),
        "brief": brief,
        "picked": pick,
        "candidates": gen["audios"],
        "model": f"ACE-Step 1.5 {brief.get('config', 'acestep-v15-turbo')} (MIT; generated music is original and cleared for commercial use per model card)",
    }
    write_json(project / "music-report.json", report)
    say({"file": str(dst), "duration": report["duration"], "candidates": len(gen["audios"]), "seed": pick["seed"]})


if __name__ == "__main__":
    main()
