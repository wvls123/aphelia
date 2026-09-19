"""Script tools for the writer agent.

    python scripts/script_check.py --project <run> [--from-json]

--from-json: rebuild script.txt from script.json beats (say concatenated) and write stress-overrides.json.
Always: checks Latin letters, digits, sentence length, estimated duration vs brief.json. Exit 1 on errors.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import read_json, say, write_json
from voice_lexicon import latin_brand_tokens

WORDS_PER_SEC = 2.35  # measured on the narrator-ru voice at tempo 1.06 (short punchy sentences)
VIEWER_JOBS = {"attention", "context", "proof", "desire", "action"}
VIEWER_JOB_ORDER = {name: i for i, name in enumerate(("attention", "context", "proof", "desire", "action"))}
SHOT_FRAMINGS = {"wide", "medium", "close", "macro", "screen", "diagram"}
SHOT_FIELDS = ("subject", "action", "framing", "continuity", "avoid")
SCRIPT_SCHEMA_VERSION = 2


def sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [p.strip() for p in re.split(r"(?<=[.!?…])\s+", flat) if p.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--from-json", action="store_true")
    args = ap.parse_args()
    project = Path(args.project)
    brief = read_json(project / "brief.json") if (project / "brief.json").exists() else {}
    errors: list[str] = []
    warnings: list[str] = []

    if args.from_json:
        sj = read_json(project / "script.json")
        beats = sj.get("beats", [])
        if not beats:
            raise SystemExit("script.json has no beats")
        text = "\n".join(b["say"].strip() for b in beats)
        (project / "script.txt").write_text(text + "\n", encoding="utf-8")
        if sj.get("stress_overrides"):
            write_json(project / "stress-overrides.json", sj["stress_overrides"])
        purposes = [b.get("purpose") for b in beats]
        for need in ("hook", "payload", "cta"):
            if need not in purposes:
                errors.append(f"script.json: no beat with purpose '{need}'")
        if purposes and purposes[0] != "hook":
            errors.append("first beat must be the hook")

        schema_version = sj.get("schema_version", 1)
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            errors.append(f"script.json: schema_version must be an integer, got {schema_version!r}")
        elif schema_version > SCRIPT_SCHEMA_VERSION:
            errors.append(
                f"script.json: unsupported future schema_version {schema_version}; max supported is {SCRIPT_SCHEMA_VERSION}"
            )
        elif schema_version < 1:
            errors.append(f"script.json: invalid schema_version {schema_version}")
        elif schema_version == 1:
            warnings.append(
                "script.json schema_version 1 (or missing): legacy run; director contract validation skipped"
            )
        else:
            beat_ids = [b.get("id") if isinstance(b, dict) else None for b in beats]
            if any(not isinstance(beat_id, str) or not beat_id.strip() for beat_id in beat_ids):
                errors.append("script.json: every beat id must be a non-empty string")
            valid_beat_ids = [beat_id for beat_id in beat_ids if isinstance(beat_id, str) and beat_id.strip()]
            if len(valid_beat_ids) != len(set(valid_beat_ids)):
                errors.append("script.json: beat ids must be unique")
            viewer_jobs: list[str] = []
            previous_shot: tuple[str, str] | None = None
            previous_label: str | int | None = None
            for i, beat in enumerate(beats):
                label = beat.get("id", i)
                viewer_job = beat.get("viewer_job")
                if not isinstance(viewer_job, str) or viewer_job not in VIEWER_JOBS:
                    errors.append(
                        f"beat '{label}': viewer_job must be one of {sorted(VIEWER_JOBS)}, got {viewer_job!r}"
                    )
                else:
                    viewer_jobs.append(viewer_job)

                shot = beat.get("shot")
                if not isinstance(shot, dict):
                    errors.append(f"beat '{label}': shot must be an object with {list(SHOT_FIELDS)}")
                    previous_shot = None
                    previous_label = None
                    continue
                missing = [field for field in SHOT_FIELDS if field not in shot]
                if missing:
                    errors.append(f"beat '{label}': shot missing fields {missing}")
                framing = shot.get("framing")
                if not isinstance(framing, str) or framing not in SHOT_FRAMINGS:
                    errors.append(
                        f"beat '{label}': shot.framing must be one of {sorted(SHOT_FRAMINGS)}, got {framing!r}"
                    )
                avoid = shot.get("avoid")
                if not isinstance(avoid, list):
                    errors.append(f"beat '{label}': shot.avoid must be a list")
                elif any(not isinstance(item, str) or not item.strip() for item in avoid):
                    errors.append(f"beat '{label}': every shot.avoid item must be a non-empty string")
                for field in ("subject", "action", "continuity"):
                    if not isinstance(shot.get(field), str) or not shot[field].strip():
                        errors.append(f"beat '{label}': shot.{field} must be a non-empty string")

                continuity = shot.get("continuity")
                current_shot = (
                    continuity if isinstance(continuity, str) else "",
                    framing if isinstance(framing, str) else "",
                )
                if previous_shot == current_shot and previous_label is not None:
                    warnings.append(
                        f"beats '{previous_label}' and '{label}' repeat continuity+framing {current_shot}"
                    )
                previous_shot = current_shot
                previous_label = label

            missing_jobs = [name for name in VIEWER_JOB_ORDER if name not in viewer_jobs]
            if missing_jobs:
                errors.append(f"script.json: missing viewer_job stages {missing_jobs}")
            order = [VIEWER_JOB_ORDER[name] for name in viewer_jobs]
            if order != sorted(order):
                errors.append(
                    "script.json: viewer_job stages must be nondecreasing: attention → context → proof → desire → action"
                )

    text = (project / "script.txt").read_text(encoding="utf-8")
    words = re.findall(r"[а-яА-ЯёЁa-zA-Z0-9]+(?:-[а-яА-ЯёЁ]+)*", text)
    latin = sorted({w for w in words if re.search(r"[a-zA-Z]", w)})
    digits = sorted({w for w in words if re.search(r"\d", w)})
    allowed = latin_brand_tokens()
    latin_blocked = [w for w in latin if w.lower() not in allowed]
    if latin_blocked:
        errors.append(f"Latin words (write them as they sound in Russian, or use an allowlisted brand): {latin_blocked}")
    if latin and not latin_blocked:
        warnings.append(f"Latin brands in say (allowed): {latin}")
    if digits:
        errors.append(f"digits (write numbers as words): {digits}")
    sents = sentences(text)
    long = [s for s in sents if len(s.split()) > 14]
    for s in long:
        warnings.append(f"long sentence ({len(s.split())} words): {s[:60]}…")
    est = len(words) / WORDS_PER_SEC
    lo, hi = brief.get("min_seconds", 60), brief.get("max_seconds", 95)
    if est < lo - 3:
        errors.append(f"too short: ~{est:.0f}s ({len(words)} words) — need {lo}–{hi}s ≈ {int(lo * WORDS_PER_SEC)}–{int(hi * WORDS_PER_SEC)} words")
    if est > hi + 3:
        errors.append(f"too long: ~{est:.0f}s ({len(words)} words) — need {lo}–{hi}s ≈ {int(lo * WORDS_PER_SEC)}–{int(hi * WORDS_PER_SEC)} words")
    fillers = [f for f in ("итак", "давайте", "в этом видео", "как вы знаете", "ну,", "э-э", "эм") if f in text.lower()]
    if fillers:
        warnings.append(f"fillers found: {fillers}")
    res = {"ok": not errors, "errors": errors, "warnings": warnings, "words": len(words), "sentences": len(sents), "est_seconds": round(est, 1), "target": [lo, hi]}
    write_json(project / "script-check.json", res)
    say(res)
    raise SystemExit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
