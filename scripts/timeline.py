"""Resolve storyboard v4 + Whisper word timings → timeline.json (single source of truth for both renderers).

Storyboard v4 (agent-authored) → absolute times for scenes, layers (incl. list/bars items), camera keys,
kinetic caption pages, SFX hits, per-scene palettes and cutout pixel sizes.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

from PIL import Image

from common import TEMPLATES, read_json, say, write_json

OVERLAP = 0.4  # seconds the previous scene keeps living under the transition
TRANSITION = {"none": 0.0, "push": 0.32, "wipe": 0.36, "fade": 0.3, "flip": 0.4, "clock": 0.42, "iris": 0.4, "zoom": 0.36, "flash": 0.24, "slice": 0.42}
# several SFX per transition type — rotated so the same whoosh never repeats back-to-back
TRANSITION_SFX = {
    "push": ["whoosh", "swoosh", "whoosh-deep", "sweep"],
    "wipe": ["sweep", "warp", "swoosh"],
    "fade": ["whoosh-deep", "paper-slide"],
    "flip": ["paper-slide", "swoosh", "paper"],
    "clock": ["sweep", "snap", "tick"],
    "iris": ["swoosh", "zoom-in", "pop"],
    "zoom": ["zoom-fast", "zoom-in", "whoosh-big"],
    "flash": ["snap", "shutter", "glitch"],
    "slice": ["warp", "sweep", "glass"],
}
WORD_LEAD = 0.06
PALETTES = {
    "paper": {"bg": "#FFFFFF", "ink": "#111111", "muted": "#6B7280", "grid": "#d8dce2"},
    "ink": {"bg": "#111111", "ink": "#FFFFFF", "muted": "#A1A1AA", "grid": "#2c2c2c"},
    "accent": {"bg": "#C8FF3D", "ink": "#111111", "muted": "#4B5320", "grid": "#a9d92f"},
    "danger": {"bg": "#FF3B30", "ink": "#FFFFFF", "muted": "#FFD5D2", "grid": "#e0332a"},
}
LAYER_TYPES = {"kicker", "headline", "stamp", "label", "bignum", "image", "arrow", "video", "list", "quote", "bars", "check", "scribble", "shape", "waveform", "lottie", "custom"}
IMAGE_ANIMS = {"pop", "wipe", "slide", "run", "shake", "swing", "zoomin", "drop", "spring", "spin"}
HEADLINE_ANIMS = {"rise", "slam", "typewriter", "words", "blur", "flip"}
SHAPES = {"circle", "star", "burst", "triangle", "pie", "ellipse"}

# ---------- russian numbers → words (for aligning Whisper digits) ----------

_UNITS = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_UNITS_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _triplet(n: int, feminine: bool = False) -> list[str]:
    out: list[str] = []
    h, rem = divmod(n, 100)
    if h:
        out.append(_HUNDREDS[h])
    if 10 <= rem < 20:
        out.append(_TEENS[rem - 10])
    else:
        t, u = divmod(rem, 10)
        if t:
            out.append(_TENS[t])
        if u:
            out.append((_UNITS_F if feminine else _UNITS)[u])
    return out


def num_to_words(n: int) -> list[str]:
    if n == 0:
        return ["ноль"]
    words: list[str] = []
    millions, rest = divmod(n, 1_000_000)
    if millions:
        words += _triplet(millions)
        words.append("миллион" if millions % 10 == 1 and millions % 100 != 11 else "миллиона" if 2 <= millions % 10 <= 4 and not 12 <= millions % 100 <= 14 else "миллионов")
    thousands, rest = divmod(rest, 1000)
    if thousands:
        words += _triplet(thousands, feminine=True)
        if thousands % 10 == 1 and thousands % 100 != 11:
            words.append("тысяча")
        elif 2 <= thousands % 10 <= 4 and not 12 <= thousands % 100 <= 14:
            words.append("тысячи")
        else:
            words.append("тысяч")
    words += _triplet(rest)
    return words


def norm(token: str) -> str:
    return re.sub(r"[^а-яa-z0-9]", "", token.lower().replace("ё", "е").replace("\u0301", ""))


def tokenize(text: str) -> list[str]:
    parts = re.split(r"[\s\-—–]+", text)
    return [p for p in (norm(p) for p in parts) if p]


def expand_whisper(words: list[dict]) -> list[dict]:
    """Whisper emits digits ('1200'); expand to number words with split timing."""
    out: list[dict] = []
    for w in words:
        n = norm(str(w["text"]))
        if not n:
            continue
        if n.isdigit() and len(n) <= 9:
            parts = num_to_words(int(n))
            span = (w["end"] - w["start"]) / max(1, len(parts))
            for i, p in enumerate(parts):
                out.append({"text": p, "start": w["start"] + i * span, "end": w["start"] + (i + 1) * span})
        else:
            for p in re.split(r"[\-—–]", n):
                if p:
                    out.append({"text": p, "start": w["start"], "end": w["end"]})
    return out


def align_script(script_tokens: list[str], heard: list[dict]) -> list[dict]:
    heard_tokens = [h["text"] for h in heard]
    sm = difflib.SequenceMatcher(None, script_tokens, heard_tokens, autojunk=False)
    timed: list[dict | None] = [None] * len(script_tokens)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                timed[i1 + k] = {"start": heard[j1 + k]["start"], "end": heard[j1 + k]["end"]}
        elif tag == "replace":
            span_start = heard[j1]["start"]
            span_end = heard[j2 - 1]["end"]
            n = i2 - i1
            step = (span_end - span_start) / n
            for k in range(n):
                timed[i1 + k] = {"start": span_start + k * step, "end": span_start + (k + 1) * step}
    for i, t in enumerate(timed):
        if t is not None:
            continue
        prev_end = next((timed[j]["end"] for j in range(i - 1, -1, -1) if timed[j]), 0.0)
        nxt = next((timed[j]["start"] for j in range(i + 1, len(timed)) if timed[j]), prev_end + 0.3)
        timed[i] = {"start": prev_end, "end": max(prev_end + 0.05, nxt)}
    return [{"text": tok, **t} for tok, t in zip(script_tokens, timed)]  # type: ignore[arg-type]


# ---------- resolution ----------

def _find_word_time(scene_words: list[dict], word: str, scene_id: str) -> float:
    target = norm(word)
    for w in scene_words:
        if w["text"] == target or w["text"].startswith(target) or target.startswith(w["text"]):
            return max(0.0, w["start"] - WORD_LEAD)
    raise SystemExit(f"[{scene_id}] at_word '{word}' not found in scene words {[w['text'] for w in scene_words]}")


def _resolve_at(item: dict, scene_start: float, scene_words: list[dict], scene_id: str) -> float:
    if "at_word" in item:
        return round(_find_word_time(scene_words, item["at_word"], scene_id), 3)
    return round(scene_start + float(item.get("at", 0.0)), 3)


def parse_number(value: object) -> dict:
    """'6 $' / '0,69' / '1 200 %' → prefix, num, decimals, suffix (count-ups keep units and decimals)."""
    s = str(value).strip()
    m = re.match(r"^([^\d\-]*)(-?[\d\s]+(?:[.,]\d+)?)(.*)$", s)
    if not m:
        try:
            return {"prefix": "", "num": float(s), "decimals": 0, "suffix": ""}
        except ValueError:
            return {"prefix": s, "num": 0.0, "decimals": 0, "suffix": ""}
    raw = re.sub(r"\s", "", m.group(2)).replace(",", ".")
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return {"prefix": m.group(1), "num": float(raw), "decimals": decimals, "suffix": m.group(3)}


def _image_size(assets: Path, layer: dict) -> tuple[int, int]:
    with Image.open(assets / layer["src"]) as im:
        iw, ih = im.size
    if "w" in layer and "h" in layer:
        return int(layer["w"]), int(layer["h"])
    if "w" in layer:
        return int(layer["w"]), round(layer["w"] * ih / iw)
    return round(layer["h"] * iw / ih), int(layer["h"])


def build_captions(words: list[dict], cfg: dict) -> list[dict]:
    pages: list[list[dict]] = []
    cur: list[dict] = []
    max_words = int(cfg.get("max_words", 3))
    max_sec = float(cfg.get("max_sec", 1.1))
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[0]["start"] > max_sec or cur[-1].get("break")):
            pages.append(cur)
            cur = []
        cur.append(w)
    if cur:
        pages.append(cur)
    out: list[dict] = []
    for i, page in enumerate(pages):
        start = page[0]["start"]
        end = pages[i + 1][0]["start"] - 0.02 if i + 1 < len(pages) else page[-1]["end"] + 0.6
        out.append(
            {
                "start": round(start, 3),
                "end": round(max(end, start + 0.1), 3),
                "words": [{"text": w["display"], "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in page],
            }
        )
    return out


def resolve_layer(raw: dict, sc: dict, sw: list[dict], assets: Path) -> dict:
    layer = dict(raw)
    sid = sc["id"]
    layer["t"] = _resolve_at(raw, sc["start"], sw, sid)
    layer.pop("at", None)
    layer.pop("at_word", None)
    layer["until"] = sc["end"]
    kind = layer["type"]
    if kind not in LAYER_TYPES:
        raise SystemExit(f"[{sid}] unknown layer type {kind}")
    if kind == "image":
        layer["w"], layer["h"] = _image_size(assets, layer)
        layer.setdefault("anim", "pop")
        if layer["anim"] not in IMAGE_ANIMS:
            raise SystemExit(f"[{sid}] unknown image anim {layer['anim']}")
        layer.setdefault("dur", 1.0 if layer["anim"] == "run" else 0.45)
        layer.setdefault("float", False)
        layer.setdefault("from", "right")
        layer.setdefault("to_x", layer["x"])
        layer.setdefault("trail", False)
    elif kind == "arrow":
        layer.setdefault("dur", 0.32)
        layer.setdefault("bend", 0.0)
        layer.setdefault("width", 10)
        layer.setdefault("color", "ink")
    elif kind == "bignum":
        layer.setdefault("color", "ink")
        layer.setdefault("deco", "none")
        layer.setdefault("deco_color", "accent")
        layer.setdefault("label", "")
        layer["digits"] = int(re.sub(r"\D", "", layer["value"]) or 0)
        layer["number"] = parse_number(layer["value"])
    elif kind == "headline":
        layer.setdefault("color", "ink")
        layer.setdefault("hl", [])
        layer.setdefault("anim", "rise")
        layer.setdefault("lines", 3)
        if layer["anim"] not in HEADLINE_ANIMS:
            raise SystemExit(f"[{sid}] unknown headline anim {layer['anim']}")
    elif kind in ("kicker", "stamp", "label"):
        layer.setdefault("color", "muted" if kind == "kicker" else "ink" if kind == "stamp" else "accent")
        layer.setdefault("rot", 0)
        layer.setdefault("size", 150 if kind == "stamp" else 44)
    elif kind == "list":
        layer.setdefault("size", 52)
        layer.setdefault("bullet", "check")
        layer.setdefault("color", "ink")
        items = []
        for it in layer["items"]:
            item = dict(it)
            item["t"] = _resolve_at(it, sc["start"], sw, sid) if ("at" in it or "at_word" in it) else layer["t"]
            item.pop("at", None)
            item.pop("at_word", None)
            items.append(item)
        layer["items"] = items
    elif kind == "quote":
        layer.setdefault("size", 64)
        layer.setdefault("color", "ink")
        layer.setdefault("author", "")
    elif kind == "bars":
        layer.setdefault("size", 40)
        layer.setdefault("color", "ink")
        parsed = [parse_number(it["value"]) for it in layer["items"]]
        mx = max(p["num"] for p in parsed) or 1.0
        items = []
        for it, p in zip(layer["items"], parsed):
            item = dict(it)
            item.setdefault("color", "accent")
            item["number"] = p
            item["frac"] = round(p["num"] / float(layer.get("max", mx)), 4)
            item["t"] = _resolve_at(it, sc["start"], sw, sid) if ("at" in it or "at_word" in it) else layer["t"]
            item.pop("at", None)
            item.pop("at_word", None)
            items.append(item)
        layer["items"] = items
    elif kind == "check":
        layer.setdefault("kind", "check")
        layer.setdefault("size", 220)
        layer.setdefault("color", "accent" if layer["kind"] == "check" else "danger")
    elif kind == "scribble":
        layer.setdefault("shape", "circle")
        layer.setdefault("color", "danger")
        layer.setdefault("width", 10)
        layer.setdefault("dur", 0.45)
    elif kind == "video":
        layer.setdefault("rot", 0)
        layer.setdefault("url", "")
        layer["seek"] = float(layer.get("seek", 0.0))  # offset into the source clip
        if not (assets / layer["src"]).exists():
            raise SystemExit(f"[{sid}] video not found: assets/{layer['src']}")
    elif kind == "shape":
        layer.setdefault("shape", "burst")
        if layer["shape"] not in SHAPES:
            raise SystemExit(f"[{sid}] unknown shape {layer['shape']}")
        layer.setdefault("size", 300)
        layer.setdefault("color", "accent")
        layer.setdefault("anim", "pop")
        layer.setdefault("progress", 1.0)
        layer.setdefault("points", 5 if layer["shape"] == "star" else 14)
        layer.setdefault("rot", 0)
    elif kind == "waveform":
        layer.setdefault("src", "vo.mp3")
        layer.setdefault("w", 600)
        layer.setdefault("h", 240)
        layer.setdefault("bars", 32)
        layer.setdefault("color", "accent")
    elif kind == "lottie":
        layer.setdefault("loop", True)
        layer.setdefault("speed", 1.0)
        layer.setdefault("w", 400)
        layer.setdefault("h", 400)
        if not (assets / layer["src"]).exists():
            raise SystemExit(f"[{sid}] lottie json not found: assets/{layer['src']}")
    elif kind == "custom":
        if not layer.get("component"):
            raise SystemExit(f"[{sid}] custom layer needs 'component'")
        layer.setdefault("props", {})
    return layer


def build(project: Path) -> dict:
    sb = read_json(project / "storyboard.json")
    assets = project / "assets"
    script = (project / sb.get("script_file", "script.txt")).read_text(encoding="utf-8").strip()
    words_payload = read_json(assets / "vo-words.json")
    heard = expand_whisper(words_payload["words"])
    duration = float((assets / "vo-duration.txt").read_text(encoding="utf-8").strip())

    display_tokens = [t for t in re.split(r"\s+", script) if t and re.search(r"[а-яА-ЯёЁa-zA-Z0-9]", t)]
    script_tokens: list[str] = []
    token_owner: list[int] = []
    for i, d in enumerate(display_tokens):
        for part in tokenize(d):
            script_tokens.append(part)
            token_owner.append(i)
    aligned = align_script(script_tokens, heard)

    words: list[dict] = []
    for i, d in enumerate(display_tokens):
        subs = [a for a, o in zip(aligned, token_owner) if o == i]
        words.append(
            {
                "display": d.strip("«»\"'"),
                "text": norm(d),
                "start": subs[0]["start"],
                "end": subs[-1]["end"],
                "break": d.endswith((".", "!", "?", ":", ",", "…")),
            }
        )

    cursor = 0
    scenes: list[dict] = []
    for sc in sb["scenes"]:
        n = len([t for t in re.split(r"\s+", sc["say"]) if t and re.search(r"[а-яА-ЯёЁa-zA-Z0-9]", t)])
        scene_words = words[cursor: cursor + n]
        if not scene_words:
            raise SystemExit(f"[{sc['id']}] scene has no words (say/script mismatch)")
        cursor += n
        start = 0.0 if not scenes else max(0.0, scene_words[0]["start"] - WORD_LEAD)
        scenes.append({**sc, "_words": scene_words, "start": round(start, 3)})
    if cursor != len(words):
        raise SystemExit(f"say/script mismatch: consumed {cursor} of {len(words)} words")
    for i, sc in enumerate(scenes):
        nxt = scenes[i + 1]["start"] if i + 1 < len(scenes) else duration
        sc["end"] = round(min(duration, nxt + OVERLAP), 3)
        sc["next_start"] = round(nxt, 3)

    style = dict(sb["style"])
    manifest = read_json(TEMPLATES / "audio" / "manifest.json")
    out_scenes: list[dict] = []
    sfx_global: list[dict] = []
    tr_counter: dict[str, int] = {}
    for sc in scenes:
        sw = sc["_words"]
        tr = dict(sc.get("transition", {"type": "none"}))
        if tr["type"] not in TRANSITION:
            raise SystemExit(f"[{sc['id']}] unknown transition {tr['type']}")
        tr["dur"] = TRANSITION[tr["type"]]
        tr.setdefault("dir", "left")
        tr.setdefault("from", [540, 960])
        pal_name = sc.get("bg", "paper")
        if pal_name not in PALETTES:
            raise SystemExit(f"[{sc['id']}] unknown bg palette {pal_name}")
        palette = {**PALETTES[pal_name], "accent": style["accent"], "danger": style["danger"], "name": pal_name}
        if pal_name == "accent":
            palette["accent"] = "#FFFFFF"
        if pal_name == "danger":
            palette["danger"] = "#111111"
        layers = [resolve_layer(raw, sc, sw, assets) for raw in sc["layers"]]
        cam: list[dict] = []
        for k in sc.get("camera", [{"at": 0, "zoom": 1.0}]):
            cam.append(
                {
                    "t": _resolve_at(k, sc["start"], sw, sc["id"]),
                    "zoom": float(k.get("zoom", 1.0)),
                    "x": float(k.get("x", 540)),
                    "y": float(k.get("y", 960)),
                    "ease": k.get("ease", "smooth"),
                    "shake": float(k.get("shake", 0)),
                }
            )
        cam.sort(key=lambda k: k["t"])
        for hit in sc.get("sfx", []):
            if hit["name"] not in manifest["sfx"]:
                raise SystemExit(f"[{sc['id']}] unknown sfx {hit['name']}; see templates/audio/manifest.json")
            sfx_global.append({"name": hit["name"], "t": _resolve_at(hit, sc["start"], sw, sc["id"]), "vol": float(hit.get("vol", 0.5)), "len": manifest["sfx"][hit["name"]]})
        if tr["type"] in TRANSITION_SFX and sc["start"] > 0:
            variants = TRANSITION_SFX[tr["type"]]
            name = tr.get("sfx") or variants[tr_counter.get(tr["type"], 0) % len(variants)]
            tr_counter[tr["type"]] = tr_counter.get(tr["type"], 0) + 1
            if name not in manifest["sfx"]:
                raise SystemExit(f"[{sc['id']}] unknown transition sfx {name}")
            sfx_global.append({"name": name, "t": round(sc["start"], 3), "vol": float(tr.get("sfx_vol", 0.42)), "len": manifest["sfx"][name]})
        out_scenes.append(
            {
                "id": sc["id"],
                "start": sc["start"],
                "end": sc["end"],
                "next_start": sc["next_start"],
                "transition": tr,
                "palette": palette,
                "layers": layers,
                "camera": cam,
                "words": [{"text": w["display"], "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in sw],
                "motion_blur": bool(sc.get("motion_blur", any(k["ease"] == "crash" or k["shake"] > 0 for k in cam))),
                "handheld": float(sc.get("handheld", 0.0)),
            }
        )
    sfx_global.sort(key=lambda h: h["t"])

    bgm = sb.get("bgm")
    if bgm:
        bgm = dict(bgm)
        stem = Path(bgm["src"]).stem
        generated = assets / "audio" / f"{stem}.mp3"
        is_generated = stem == "bgm-generated" and (project / "music-brief.json").exists()  # render.py generates it
        if stem not in manifest["bgm"] and not generated.exists() and not is_generated:
            raise SystemExit(f"unknown bgm {bgm['src']}: not in templates/audio/manifest.json and no assets/audio/{stem}.mp3 (run scripts/music.py)")
        bgm["src"] = f"audio/{stem}.mp3"
        bgm.setdefault("vol", 0.35)

    timeline = {
        "id": sb["id"],
        "fps": sb.get("fps", 30),
        "width": sb.get("width", 1080),
        "height": sb.get("height", 1920),
        "duration": round(duration, 3),
        "style": style,
        "captions_cfg": sb.get("captions", {}),
        "words": [{"text": w["display"], "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in words],
        "captions": build_captions(words, sb.get("captions", {})),
        "bgm": bgm,
        "sfx": sfx_global,
        "scenes": out_scenes,
    }
    write_json(project / "timeline.json", timeline)
    return timeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    tl = build(Path(args.project))
    say(
        {
            "duration": tl["duration"],
            "scenes": [(s["id"], s["start"], s["next_start"]) for s in tl["scenes"]],
            "caption_pages": len(tl["captions"]),
            "sfx": len(tl["sfx"]),
        }
    )


if __name__ == "__main__":
    main()
