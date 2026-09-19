"""Validate an agent-authored storyboard.json before timeline/render — schema + craft rules.

Exit code 1 on errors. Warnings are advisory (variety, pacing). Output: JSON with errors/warnings/stats
and <run>/storyboard-validation.json.

    python scripts/validate_storyboard.py --project aphelia-memory/runs/<slug>
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from common import TEMPLATES, read_json, say, write_json
from timeline import HEADLINE_ANIMS, IMAGE_ANIMS, LAYER_TYPES, PALETTES, SHAPES, TRANSITION, norm

W, H = 1080, 1920
SAFE_TOP = 180  # platform UI overlays
SAFE_BOTTOM = 1700
EST_WPS = 2.6  # narration pace used for pre-voice timing estimates
MIN_CRASH_GAP = 5.0  # seconds between two camera crashes (motion-library: 6–8 s recommended)
WAVEFORM_BARS_POW2 = {8, 16, 32, 64}  # visualizeAudio numberOfSamples must be pow2; render rounds up but prefer these
VIEWER_JOBS = {"attention", "context", "proof", "desire", "action"}
SHOT_FRAMINGS = {"wide", "medium", "close", "macro", "screen", "diagram"}
SHOT_FIELDS = ("subject", "action", "framing", "continuity", "avoid")
SCRIPT_SCHEMA_VERSION = 2


def words_of(text: str) -> list[str]:
    return [norm(t) for t in re.split(r"\s+", text) if t and re.search(r"[а-яА-ЯёЁa-zA-Z0-9]", t)]


def compact_text(text: str) -> str:
    """Preserve words, case and punctuation; normalize only whitespace."""
    return " ".join(text.split())


def word_index(scene_words: list[str], word: str) -> int | None:
    target = norm(word)
    return next((i for i, w in enumerate(scene_words) if w == target or w.startswith(target)), None)


def validate(project: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    sb = read_json(project / "storyboard.json")
    assets = project / "assets"
    manifest = read_json(TEMPLATES / "audio" / "manifest.json")
    script_json_path = project / "script.json"
    script_json = read_json(script_json_path) if script_json_path.exists() else {}
    schema_version = script_json.get("schema_version", 1)
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        errors.append(f"script.json: schema_version must be an integer, got {schema_version!r}")
        contract_v2 = False
    elif schema_version > SCRIPT_SCHEMA_VERSION:
        errors.append(
            f"script.json: unsupported future schema_version {schema_version}; max supported is {SCRIPT_SCHEMA_VERSION}"
        )
        contract_v2 = False
    elif schema_version < 1:
        errors.append(f"script.json: invalid schema_version {schema_version}")
        contract_v2 = False
    else:
        contract_v2 = schema_version == SCRIPT_SCHEMA_VERSION
    beats = script_json.get("beats", []) if contract_v2 else []
    beats_by_id = {b.get("id"): b for b in beats if isinstance(b, dict) and isinstance(b.get("id"), str)}
    expected_beat_ids = [b.get("id") for b in beats if isinstance(b, dict)]
    if contract_v2:
        if len(beats_by_id) != len(beats):
            errors.append("script.json schema v2: every beat needs a unique string id")
        if not beats:
            errors.append("script.json schema v2: beats must not be empty")

    for key in ("id", "style", "scenes"):
        if key not in sb:
            errors.append(f"missing top-level '{key}'")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    script_path = project / sb.get("script_file", "script.txt")
    if not script_path.exists():
        errors.append(f"script file not found: {script_path.name}")
        return {"ok": False, "errors": errors, "warnings": warnings}
    script_text = script_path.read_text(encoding="utf-8")
    script_words = words_of(script_text)
    say_words = [w for sc in sb["scenes"] for w in words_of(sc.get("say", ""))]
    scenes_text = " ".join(str(sc.get("say", "")) for sc in sb["scenes"])
    if compact_text(script_text) != compact_text(scenes_text):
        errors.append(
            "say/script exact mismatch after whitespace normalization "
            f"(script {len(script_words)} words, say {len(say_words)} words)"
        )

    transitions: list[str] = []
    anims: Counter[str] = Counter()
    types: Counter[str] = Counter()
    cam_scenes = 0
    scene_ids: list[str] = []
    scene_stickers: list[set[str]] = []  # image src per scene → repeats across scenes
    scene_contracts: list[tuple[str, str, str]] = []  # source beat, continuity, framing
    scene_say_by_beat: dict[str, list[str]] = {}
    scenes_by_beat: dict[str, list[dict]] = {}
    crash_times: list[tuple[float, str]] = []  # estimated (t, scene id) of every ease: crash key
    sfx_used: Counter[str] = Counter()
    word_cursor = 0
    ids = Counter(sc["id"] for sc in sb["scenes"])
    for sid, n in ids.items():
        if n > 1:
            errors.append(f"duplicate scene id '{sid}'")
    for idx, sc in enumerate(sb["scenes"]):
        sid = sc.get("id", f"#{idx}")
        sw = words_of(sc.get("say", ""))
        scene_ids.append(sid)
        scene_start_est = word_cursor / EST_WPS
        word_cursor += len(sw)
        if not sw:
            errors.append(f"[{sid}] empty say")
        if contract_v2:
            source_beat = sc.get("source_beat")
            viewer_job = sc.get("viewer_job")
            source_shot = sc.get("source_shot")
            shot = sc.get("shot")
            beat = beats_by_id.get(source_beat) if isinstance(source_beat, str) else None
            if beat is None:
                errors.append(f"[{sid}] source_beat must name one schema-v2 script beat, got {source_beat!r}")
            elif viewer_job != beat.get("viewer_job"):
                errors.append(
                    f"[{sid}] viewer_job {viewer_job!r} does not match source beat '{source_beat}' ({beat.get('viewer_job')!r})"
                )
            if beat is not None and source_shot != beat.get("shot"):
                errors.append(f"[{sid}] source_shot must exactly preserve shot from source beat '{source_beat}'")
            if not isinstance(viewer_job, str) or viewer_job not in VIEWER_JOBS:
                errors.append(f"[{sid}] unknown viewer_job {viewer_job!r}")
            if not isinstance(shot, dict):
                errors.append(f"[{sid}] shot must be an object with {list(SHOT_FIELDS)}")
                continuity, framing = "", ""
            else:
                missing = [field for field in SHOT_FIELDS if field not in shot]
                if missing:
                    errors.append(f"[{sid}] shot missing fields {missing}")
                framing_value = shot.get("framing")
                if not isinstance(framing_value, str) or framing_value not in SHOT_FRAMINGS:
                    errors.append(f"[{sid}] unknown shot.framing {framing_value!r}")
                avoid = shot.get("avoid")
                if not isinstance(avoid, list) or any(
                    not isinstance(item, str) or not item.strip() for item in avoid
                ):
                    errors.append(f"[{sid}] shot.avoid must contain only non-empty strings")
                for field in ("subject", "action", "continuity"):
                    if not isinstance(shot.get(field), str) or not shot[field].strip():
                        errors.append(f"[{sid}] shot.{field} must be a non-empty string")
                continuity = shot.get("continuity") if isinstance(shot.get("continuity"), str) else ""
                framing = framing_value if isinstance(framing_value, str) else ""
            if isinstance(source_beat, str):
                scene_say_by_beat.setdefault(source_beat, []).append(str(sc.get("say", "")))
                scenes_by_beat.setdefault(source_beat, []).append(sc)
                scene_contracts.append((source_beat, continuity, framing))
        tr = sc.get("transition", {"type": "none"})
        if tr.get("type") not in TRANSITION:
            errors.append(f"[{sid}] unknown transition '{tr.get('type')}'")
        transitions.append(tr.get("type", "none"))
        if sc.get("bg", "paper") not in PALETTES:
            errors.append(f"[{sid}] unknown bg '{sc.get('bg')}'")
        layers = sc.get("layers", [])
        if len(layers) < 2:
            warnings.append(f"[{sid}] only {len(layers)} layer(s) — scenes need at least a headline/number + a visual")
        has_visual = False
        for li, l in enumerate(layers):
            kind = l.get("type")
            if kind not in LAYER_TYPES:
                errors.append(f"[{sid}] layer {li}: unknown type '{kind}'")
                continue
            types[kind] += 1
            if kind in ("image", "video", "bars", "list", "quote", "check", "arrow", "scribble", "bignum", "shape", "waveform", "lottie", "custom"):
                has_visual = True
            if kind == "custom":
                comp = str(l.get("component", ""))
                if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", comp):
                    errors.append(f"[{sid}] layer {li}: custom component name must be PascalCase, got '{comp}'")
                elif comp != "ExampleBadge" and not (project / "custom" / f"{comp}.tsx").exists():
                    errors.append(f"[{sid}] layer {li}: custom component '{comp}' has no file <run>/custom/{comp}.tsx")
            if kind == "lottie" and not (assets / l.get("src", "")).exists():
                errors.append(f"[{sid}] layer {li}: lottie json not found assets/{l.get('src')}")
            if kind == "shape" and l.get("shape", "burst") not in SHAPES:
                errors.append(f"[{sid}] layer {li}: unknown shape '{l.get('shape')}'")
            for key in ("at_word",):
                if key in l and not any(w == norm(l[key]) or w.startswith(norm(l[key])) for w in sw):
                    errors.append(f"[{sid}] layer {li}: at_word '{l[key]}' not in say")
            if kind == "image":
                if not (assets / l.get("src", "")).exists():
                    errors.append(f"[{sid}] layer {li}: image not found assets/{l.get('src')}")
                elif not str(l["src"]).startswith("cut/"):
                    warnings.append(f"[{sid}] layer {li}: image '{l['src']}' is not a cutout (assets/cut/*) — stickers must be transparent")
                anims[l.get("anim", "pop")] += 1
                if l.get("anim", "pop") not in IMAGE_ANIMS:
                    errors.append(f"[{sid}] layer {li}: unknown image anim '{l.get('anim')}'")
                if "w" not in l and "h" not in l:
                    errors.append(f"[{sid}] layer {li}: image needs w or h")
            if kind == "video" and not (assets / l.get("src", "")).exists():
                errors.append(f"[{sid}] layer {li}: video not found assets/{l.get('src')}")
            if kind == "waveform":
                bars = int(l.get("bars", 32))
                if not 8 <= bars <= 64:
                    warnings.append(f"[{sid}] layer {li}: waveform bars={bars} — keep 8–64")
                elif bars not in WAVEFORM_BARS_POW2:
                    warnings.append(
                        f"[{sid}] layer {li}: waveform bars={bars} is not a power of two — use 16, 32 or 64 "
                        f"(visualizeAudio needs pow2 samples; render rounds up but uneven counts look wrong)"
                    )
            if kind == "headline":
                if l.get("anim", "rise") not in HEADLINE_ANIMS:
                    errors.append(f"[{sid}] layer {li}: unknown headline anim '{l.get('anim')}'")
                if len(l.get("text", "")) > 48:
                    warnings.append(f"[{sid}] layer {li}: headline longer than 48 chars — will wrap into 4+ lines")
                for ph in l.get("hl", []):
                    if ph not in l.get("text", ""):
                        errors.append(f"[{sid}] layer {li}: hl phrase '{ph}' not in headline text")
            if kind in ("list", "bars"):
                items = l.get("items", [])
                if not 2 <= len(items) <= 5:
                    warnings.append(f"[{sid}] layer {li}: {kind} with {len(items)} items (2–5 reads best)")
                for it in items:
                    if "at_word" in it and not any(w == norm(it["at_word"]) or w.startswith(norm(it["at_word"])) for w in sw):
                        errors.append(f"[{sid}] layer {li}: item at_word '{it['at_word']}' not in say")
            y = l.get("y")
            if isinstance(y, (int, float)) and kind in ("kicker", "headline") and y < SAFE_TOP:
                warnings.append(f"[{sid}] layer {li}: {kind} at y={y} sits under the platform top bar (keep y ≥ {SAFE_TOP})")
            if isinstance(y, (int, float)) and kind in ("label", "stamp", "list", "quote") and y > SAFE_BOTTOM:
                warnings.append(f"[{sid}] layer {li}: {kind} at y={y} collides with captions/bottom UI (keep y ≤ {SAFE_BOTTOM})")
        if not has_visual:
            warnings.append(f"[{sid}] no visual layer (image/list/bars/quote/check/arrow/bignum) — text-only scene")
        scene_stickers.append({str(l["src"]) for l in layers if l.get("type") == "image" and "src" in l})
        for kind in ("stamp", "bignum"):
            cnt = sum(1 for l in layers if l.get("type") == kind)
            if cnt > 1:
                warnings.append(f"[{sid}] {cnt} {kind} layers in one scene — keep at most one {kind} per scene")
        kickers = [l for l in layers if l.get("type") == "kicker"]
        heads = [l for l in layers if l.get("type") == "headline"]
        for k in kickers:
            for h in heads:
                gap = float(h.get("y", 0)) - float(k.get("y", 0))
                if 0 <= gap < float(k.get("size", 44)) * 1.3:
                    warnings.append(f"[{sid}] kicker (y {k.get('y')}) sits on the headline (y {h.get('y')}) — keep ≥ {float(k.get('size', 44)) * 1.3:.0f} px between them")
        cam = sc.get("camera", [])
        if len(cam) >= 2:
            cam_scenes += 1
        for k in cam:
            if "at_word" in k and not any(w == norm(k["at_word"]) or w.startswith(norm(k["at_word"])) for w in sw):
                errors.append(f"[{sid}] camera at_word '{k['at_word']}' not in say")
            if k.get("ease") == "crash":
                wi = word_index(sw, k["at_word"]) if "at_word" in k else None
                t = scene_start_est + (wi / EST_WPS if wi is not None else float(k.get("at", 0.0)))
                crash_times.append((t, sid))
            z = float(k.get("zoom", 1))
            if not 0.8 <= z <= 1.6:
                warnings.append(f"[{sid}] camera zoom {z} outside 0.8–1.6")
            if z > 1.0:
                # visible stage box at this key: everything outside is cropped (HUD kicker/headline excluded)
                cx, cy = float(k.get("x", 540)), float(k.get("y", 960))
                left, right = cx - 540 / z, cx + 540 / z
                top, bottom = cy - 960 / z, cy + 960 / z
                for li, l in enumerate(layers):
                    if l.get("type") not in ("label", "stamp", "bignum", "quote", "list", "bars", "check", "video"):
                        continue
                    lx, ly = float(l.get("x", 0)), float(l.get("y", 0))
                    est_w = float(l.get("w", 0)) or (len(str(l.get("text", l.get("value", "")))) * float(l.get("size", 40)) * 0.6 + 60)
                    if lx < left + 12 or lx + min(est_w, 900) > right - 12 or ly < top + 12 or ly > bottom - 80:
                        warnings.append(
                            f"[{sid}] layer {li} ({l['type']}) leaves the frame at camera zoom {z} → x {cx:.0f}: visible x {left:.0f}–{right:.0f}, y {top:.0f}–{bottom:.0f}; move the camera point or the layer"
                        )
                    # projected screen position: text under the caption band is unreadable
                    screen_y = 960 + z * (ly - cy)
                    if l.get("type") in ("label", "stamp", "bignum", "quote", "list") and 1440 <= screen_y <= 1720:
                        warnings.append(
                            f"[{sid}] layer {li} ({l['type']}) projects to screen y {screen_y:.0f} at this camera key — under the captions (1480–1700); raise y or lower the camera point"
                        )
        for li, l in enumerate(layers):
            if l.get("type") == "bignum" and l.get("deco") == "circle" and float(l.get("x", 0)) < 0.2 * float(l.get("size", 300)) + 20:
                warnings.append(f"[{sid}] layer {li}: bignum circle needs x ≥ {0.2 * float(l.get('size', 300)) + 20:.0f} (circle extends left of the digits)")
        for hit in sc.get("sfx", []):
            if hit.get("name") not in manifest["sfx"]:
                errors.append(f"[{sid}] unknown sfx '{hit.get('name')}' (see templates/audio/sfx-catalog.json)")
            else:
                sfx_used[hit["name"]] += 1
            if "at_word" in hit and not any(w == norm(hit["at_word"]) or w.startswith(norm(hit["at_word"])) for w in sw):
                errors.append(f"[{sid}] sfx at_word '{hit['at_word']}' not in say")
        if len(sc.get("sfx", [])) > 3:
            warnings.append(f"[{sid}] {len(sc['sfx'])} sfx in one scene — 0–2 is the norm, 3 max")
        if len(sw) > 26:
            warnings.append(f"[{sid}] {len(sw)} words in one scene (~{len(sw) / EST_WPS:.0f}s) — split it, reels change picture every 2–5 s")

    n = len(sb["scenes"])
    if contract_v2:
        actual_beat_ids = [source for source, _, _ in scene_contracts]
        collapsed_beat_ids = [
            source for i, source in enumerate(actual_beat_ids) if i == 0 or source != actual_beat_ids[i - 1]
        ]
        if collapsed_beat_ids != expected_beat_ids:
            errors.append(
                f"storyboard source_beat order/coverage mismatch: expected {expected_beat_ids}, got {collapsed_beat_ids}"
            )
        for beat_id, beat in beats_by_id.items():
            reconstructed = " ".join(scene_say_by_beat.get(beat_id, []))
            if compact_text(str(beat.get("say", ""))) != compact_text(reconstructed):
                errors.append(
                    f"storyboard scenes for source_beat '{beat_id}' do not exactly reproduce that beat's say"
                )
            mapped_scenes = scenes_by_beat.get(beat_id, [])
            if len(mapped_scenes) == 1 and mapped_scenes[0].get("shot") != beat.get("shot"):
                errors.append(
                    f"storyboard unsplit scene for source_beat '{beat_id}' must preserve the beat shot exactly"
                )
        for previous, current in zip(scene_contracts, scene_contracts[1:]):
            if previous[1:] == current[1:]:
                warnings.append(
                    f"scenes for '{previous[0]}' → '{current[0]}' repeat continuity+framing {current[1:]}"
                )
    # motion-library rule 6: no sticker in two adjacent scenes, one sticker ≤ 2 scenes per reel
    for i in range(1, len(scene_stickers)):
        for src in sorted(scene_stickers[i] & scene_stickers[i - 1]):
            warnings.append(f"[{scene_ids[i]}] sticker '{src}' repeats from the previous scene [{scene_ids[i - 1]}] — adjacent scenes need different stickers")
    sticker_scenes: Counter[str] = Counter(src for stickers in scene_stickers for src in stickers)
    for src, cnt in sorted(sticker_scenes.items()):
        if cnt > 2:
            warnings.append(f"sticker '{src}' appears in {cnt} scenes — use one sticker at most twice per reel")
    # crash cadence: two camera crashes closer than MIN_CRASH_GAP feel like nausea (estimate at EST_WPS words/s)
    crash_times.sort()
    for (t0, s0), (t1, s1) in zip(crash_times, crash_times[1:]):
        if t1 - t0 < MIN_CRASH_GAP:
            warnings.append(f"camera crash in [{s1}] ~{t1 - t0:.1f}s after crash in [{s0}] — keep ≥ {MIN_CRASH_GAP:.0f} s (6–8 s recommended) between crashes; use shake or smooth instead")
    for a, b in zip(transitions[1:], transitions[2:]):
        if a == b and a != "none":
            warnings.append(f"transition '{a}' repeated back-to-back — vary transitions")
            break
    distinct_tr = {t for t in transitions[1:] if t != "none"}
    if n >= 6 and len(distinct_tr) < 3:
        warnings.append(f"only {len(distinct_tr)} distinct transition types across {n} scenes — use ≥3 (push/wipe/fade/flip/clock/iris/zoom/flash/slice)")
    if n >= 6 and cam_scenes < n * 0.5:
        warnings.append(f"camera moves in {cam_scenes}/{n} scenes — add zoom/pan keys (crash on the punch word) to at least half")
    if anims and len(anims) < 3 and sum(anims.values()) >= 5:
        warnings.append(f"image anims used: {dict(anims)} — vary (pop/slide/swing/drop/zoomin/wipe/run/shake)")
    for name, cnt in sorted(sfx_used.items()):
        if cnt > 3:
            warnings.append(f"sfx '{name}' used {cnt} times — pick different sounds by meaning (templates/audio/sfx-catalog.json), same sound ≤ 3 per reel")
    if not sb.get("bgm"):
        warnings.append("no bgm — every reel needs a bed: generated (audio/bgm-generated.mp3 + music-brief.json) or a library track")
    else:
        stem = Path(sb["bgm"]["src"]).stem
        if stem == "bgm-generated":
            if not (project / "music-brief.json").exists():
                errors.append("bgm is audio/bgm-generated.mp3 but <run>/music-brief.json is missing (caption, bpm for ACE-Step)")
        elif stem not in manifest["bgm"] and not (assets / "audio" / f"{stem}.mp3").exists():
            errors.append(f"unknown bgm '{sb['bgm']['src']}'")
        vol = float(sb["bgm"].get("vol", 0.35))
        if not 0.2 <= vol <= 0.5:
            warnings.append(f"bgm vol {vol} — keep 0.25–0.45 so the bed never fights the voice")
    bgs = Counter(sc.get("bg", "paper") for sc in sb["scenes"])
    if n >= 8 and len(bgs) == 1:
        warnings.append("all scenes on the same background — invert 1–3 punch scenes with bg: 'ink' or 'accent'")
    if str(sb["style"].get("accent", "")).upper() == "#C8FF3D" and sb.get("style_preset") not in (None, "whiteboard-lime"):
        warnings.append("accent is still the default lime — the style preset should set its own accent (vary colour reel to reel)")
    cap = sb.get("captions") or {}
    cap_style = cap.get("style", "box")
    if cap_style == "karaoke":
        long_scenes = sum(1 for sc in sb["scenes"] if len(words_of(sc.get("say", ""))) > 4)
        if long_scenes >= 3:
            warnings.append(
                f"captions.style karaoke with {long_scenes} scenes over 4 words — words glue on long pages; "
                f"use box/outline or max_sec ≤ 0.75 (see motion-library)"
            )
    stats = {"scenes": n, "words": len(say_words), "est_seconds": round(len(say_words) / EST_WPS, 1), "transitions": dict(Counter(transitions)), "layer_types": dict(types), "image_anims": dict(anims), "bgs": dict(bgs), "camera_scenes": cam_scenes, "sfx_distinct": len(sfx_used), "style_preset": sb.get("style_preset")}
    result = {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}
    write_json(project / "storyboard-validation.json", result)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    res = validate(Path(args.project))
    say(res)
    raise SystemExit(0 if res["ok"] else 1)
