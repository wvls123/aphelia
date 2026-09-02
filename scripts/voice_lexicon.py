"""Durable voice lexicon: ruaccent extras, Qwen force-marks, brand Latin rewrite."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from common import PLUGIN_ROOT

LEXICON_PATH = PLUGIN_ROOT / "shared" / "voice-lexicon.json"


@lru_cache(maxsize=1)
def load() -> dict:
    if not LEXICON_PATH.exists():
        return {
            "qwen_force_marks": [],
            "ruaccent_custom_dict": {},
            "latin_brands": [],
            "phonetics": {},
            "cyrillic_to_latin": {},
        }
    return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))


def ruaccent_custom_dict() -> dict[str, str]:
    """Loanwords / inflections ruaccent gets wrong. Passed to RUAccent.load(custom_dict=...)."""
    data = load()
    merged = dict(data.get("ruaccent_custom_dict") or {})
    merged.update(data.get("stress_overrides") or {})  # leftover key from older lexicons
    return merged


def force_mark_words() -> set[str]:
    """Words Qwen mispronounces: keep U+0301. Stress position comes from ruaccent, not this list."""
    data = load()
    words: set[str] = set()
    for w in data.get("qwen_force_marks") or []:
        words.add(str(w).lower())
    for key, marked in ruaccent_custom_dict().items():
        words.add(key.lower())
        words.add(marked.replace("+", "").lower())
    return words


def latin_brand_tokens() -> set[str]:
    tokens: set[str] = set()
    for brand in load().get("latin_brands") or []:
        for part in re.split(r"[\s/\-]+", brand):
            if re.search(r"[A-Za-z]", part):
                tokens.add(part.lower())
    return tokens


def apply_latin_for_tts(text: str) -> str:
    """Rewrite known Cyrillic brand spellings to Latin for multilingual TTS."""
    mapping: dict[str, str] = dict(load().get("cyrillic_to_latin") or {})
    items = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
    out = text
    for src, latin in items:
        out = re.sub(re.escape(src), latin, out, flags=re.IGNORECASE)
    return out


def fold_latin_brands_to_cyrillic(text: str) -> str:
    """Map Latin brand names to Cyrillic phonetics so Whisper compare is not letter-spelled."""
    phonetics: dict[str, str] = dict(load().get("phonetics") or {})
    items = sorted(phonetics.items(), key=lambda kv: len(kv[0]), reverse=True)
    out = text
    for latin, cyr in items:
        out = re.sub(rf"(?i)(?<![A-Za-z]){re.escape(latin)}(?![A-Za-z])", cyr, out)
    return out
