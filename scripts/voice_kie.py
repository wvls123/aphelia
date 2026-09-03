"""Voice adapter: kie.ai (Google Gemini 3.1 Flash TTS) + local faster-whisper alignment,
in place of Qwen3-TTS (needs GPU we don't have in this sandbox).

Why Gemini TTS and not ElevenLabs multilingual-v2 (which has native `timestamps=true`,
would need no local alignment step): on 2026-09-03 the elevenlabs/* endpoints on kie.ai
returned 500 / stuck "waiting" for text-to-speech-turbo-2-5, text-to-speech-multilingual-v2
and text-to-dialogue-v3 (confirmed 3x, credits were charged despite no result). Retry that
path first if it comes back — it's a strictly better fit (native word timestamps, real
voice cloning). This adapter is the working fallback.

Input:  <run>/script.txt (plain narration text, same as scripts/voice.py narrate expects)
Output: <run>/assets/vo.mp3 (48kHz), <run>/assets/vo-words.json (word timestamps,
        SAME SCHEMA as scripts/voice.py's align(): {"text":..., "words":[{"text","start","end"}]}),
        <run>/assets/vo-duration.txt, <run>/voice-report.json

Usage:
    python scripts/voice_kie.py narrate --project aphelia-memory/runs/<slug> \
        [--voice-name Kore] [--speaker-id "Speaker 1"] [--tempo 1.06]

Known gaps vs scripts/voice.py (documented, not silently hidden):
- No ruaccent stress marks / qwen_force_marks / stress-overrides.json handling —
  Gemini TTS takes plain text, no acute-mark protocol.
- No per-sentence Whisper-verify-and-retry loop for mispronunciations — this adapter
  synthesizes the whole script in one call and aligns after the fact. A wrong word is
  only caught by whoever listens to voice-report.json, not auto-retried.
- No persistent brand-voice reference (VoiceDesign) — `--voice-name` picks a stock
  Gemini voice, not a cloned one. Same voice name = same timbre across reels, but it
  is not "our" custom voice.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffprobe_duration, run_dir, write_json  # noqa: E402

DEFAULT_VOICE_NAME = "Kore"
DEFAULT_SPEAKER_ID = "Speaker 1"


def kie_tts(text: str, voice_name: str, speaker_id: str, out_wav: Path) -> None:
    """Call kie.ai google/gemini-3-1-flash-tts via the velsvisual CLI, download the wav."""
    speakers = json.dumps([{"speaker_id": speaker_id, "voice_name": voice_name}], ensure_ascii=False)
    turns = json.dumps([{"speaker_id": speaker_id, "text": text}], ensure_ascii=False)
    with tempfile.TemporaryDirectory() as td:
        cmd = [
            "velsvisual", "run", "google/gemini-3-1-flash-tts",
            "--set", f"speakers={speakers}",
            "--set", f"dialogue_turns={turns}",
            "--wait", "--timeout", "180", "--download", td, "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"kie TTS failed: {result.stdout}\n{result.stderr}")
        downloaded = sorted(Path(td).glob("*.wav")) or sorted(Path(td).glob("*.mp3"))
        if not downloaded:
            raise SystemExit(f"kie TTS: no audio file downloaded. stdout={result.stdout}")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        Path(downloaded[0]).replace(out_wav)


def align(wav_path: Path, words_path: Path, model_name: str = "small") -> dict:
    """Word-level timestamps via local faster-whisper. Same output schema as voice.py's align()."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(wav_path), word_timestamps=True, language="ru")
    words = []
    full_text = []
    for seg in segments:
        full_text.append(seg.text)
        for w in seg.words or []:
            words.append({"text": w.word.strip(), "start": round(float(w.start), 3), "end": round(float(w.end), 3)})
    payload = {"text": "".join(full_text).strip(), "words": words}
    write_json(words_path, payload)
    return payload


def tighten(raw: Path, out_wav: Path, out_mp3: Path, tempo: float) -> float:
    """Same post-chain as voice.py's tighten(): tempo, loudnorm -15 LUFS, tail pad."""
    chain = f"atempo={tempo},loudnorm=I=-15:TP=-1.2:LRA=9,apad=pad_dur=0.35"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-af", chain, "-ar", "48000", str(out_wav)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(out_wav), "-b:a", "192k", str(out_mp3)],
        check=True,
    )
    return ffprobe_duration(out_wav)


def narrate(args: argparse.Namespace) -> None:
    project = Path(args.project)
    script_path = project / args.script
    if not script_path.exists():
        raise SystemExit(f"script not found: {script_path}")
    text = script_path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"script is empty: {script_path}")

    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    raw = assets / "vo-raw.wav"

    print(f"+ kie.ai google/gemini-3-1-flash-tts ({len(text)} chars)", flush=True)
    kie_tts(text, args.voice_name, args.speaker_id, raw)

    duration = tighten(raw, assets / "vo.wav", assets / "vo.mp3", args.tempo)
    report = {
        "engine": "kie.ai/google/gemini-3-1-flash-tts",
        "voice_name": args.voice_name,
        "duration": round(duration, 2),
        "tempo": args.tempo,
    }
    if not args.skip_align:
        words = align(assets / "vo.wav", assets / "vo-words.json", args.whisper_model)
        report["words"] = len(words["words"])
    else:
        report["words"] = 0
    (assets / "vo-duration.txt").write_text(f"{duration:.3f}", encoding="ascii")
    write_json(project / "voice-report.json", report)
    print(json.dumps(report, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("narrate", help="script.txt -> assets/vo.mp3 + vo-words.json + voice-report.json (kie.ai engine)")
    n.add_argument("--project", required=True, help="run directory (contains script.txt), or slug (resolved via run_dir)")
    n.add_argument("--script", default="script.txt")
    n.add_argument("--voice-name", default=DEFAULT_VOICE_NAME)
    n.add_argument("--speaker-id", default=DEFAULT_SPEAKER_ID)
    n.add_argument("--tempo", type=float, default=1.06)
    n.add_argument("--whisper-model", default="small")
    n.add_argument("--skip-align", action="store_true")

    args = ap.parse_args()
    if args.cmd == "narrate":
        project = Path(args.project)
        if not project.exists():
            project = run_dir(args.project)
        args.project = str(project)
        narrate(args)


if __name__ == "__main__":
    main()
