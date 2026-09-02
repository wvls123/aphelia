"""Aphelia voice: Russian narration with Qwen3-TTS (latest 12Hz-1.7B family), stress marks and self-verification.

Pipeline per run:
  1. Brand voice reference (once): Qwen3-TTS VoiceDesign designs a natural narrator from a
     text description; the best take (verified by Whisper, fastest clean delivery) is saved to
     voices/<name>/ref.wav + ref.txt. Cloning that reference keeps the timbre identical across
     every sentence and every future reel.
  2. Stress marks: the ruaccent library (turbo3.1 + dictionary) places '+' before the stressed
     vowel (context-aware for homographs: зАмок/замОк). Loanwords it misses live in
     voice-lexicon.json → ruaccent_custom_dict. We convert to combining acute U+0301 — the
     only notation the Base model honours — and put the same notation into the reference text.
  3. Every sentence is generated separately, trimmed, transcribed by Whisper (text similarity),
     and stress-checked with MMS forced alignment (stressed vowel = longest/loudest). Bad takes
     are regenerated; if marks keep breaking a sentence, an unmarked take is tried.
  4. Sentences are joined with short gaps, tightened (tempo, loudnorm) and aligned to word
     timestamps for the storyboard (`at_word`).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from common import VOICES, ffprobe_duration, say, sh, write_json
from voice_lexicon import (
    apply_latin_for_tts,
    fold_latin_brands_to_cyrillic,
    force_mark_words,
    ruaccent_custom_dict,
)

VOWELS = "аеёиоуыэюя"
ACUTE = "\u0301"
NUMBER_WORDS = {
    "ноль", "один", "одна", "одного", "одной", "два", "две", "двух", "три", "трех", "четыре", "четырех", "пять", "пяти",
    "шесть", "шести", "семь", "семи", "восемь", "восьми", "девять", "девяти", "десять", "десяти", "одиннадцать",
    "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать",
    "девятнадцать", "двадцать", "двадцати", "тридцать", "тридцати", "сорок", "сорока", "пятьдесят", "пятидесяти",
    "шестьдесят", "шестидесяти", "семьдесят", "семидесяти", "восемьдесят", "восьмидесяти", "девяносто", "девяноста",
    "сто", "ста", "двести", "двухсот", "триста", "трехсот", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот",
    "девятьсот", "тысяча", "тысячи", "тысяч", "миллион", "миллиона", "миллионов", "миллиард", "миллиарда", "миллиардов",
    "процент", "процента", "процентов",
}
TRANS = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "o", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

DEFAULT_VOICE = "narrator-ru"
DEFAULT_DESIGN = (
    "A charismatic native Russian male narrator, early thirties. Warm confident baritone, crisp clear diction, "
    "fast energetic delivery of a tech-news reel host, playful intrigue, no filler sounds, no hesitation, "
    "natural human breathing, studio quality."
)
DEFAULT_REF_TEXT = (
    "Привет! Сегодня разберём главную новость недели — коротко, по делу и без лишних слов. "
    "Смотри до конца: в финале будет вывод, который сэкономит тебе кучу времени."
)


# ---------- text utils ----------

LATIN_NAMES = {
    "a": "эй", "b": "би", "c": "си", "d": "ди", "e": "и", "f": "эф", "g": "джи", "h": "эйч", "i": "ай", "j": "джей",
    "k": "кей", "l": "эл", "m": "эм", "n": "эн", "o": "оу", "p": "пи", "q": "кью", "r": "ар", "s": "эс", "t": "ти",
    "u": "ю", "v": "ви", "w": "даблю", "x": "икс", "y": "уай", "z": "зед",
}


def normalize(text: str) -> str:
    """Lower-case Cyrillic word soup without numerals; known Latin brands fold to phonetics
    (GitHub → гитхаб) so they are not spelled letter-by-letter. Remaining Latin acronyms
    Whisper emits ('LTX') are spelled out ('эл ти икс')."""
    text = fold_latin_brands_to_cyrillic(strip_marks(text))
    text = text.lower().replace("ё", "е")
    tokens: list[str] = []
    for tok in re.findall(r"[а-я]+|[a-z]+", text):
        if re.fullmatch(r"[a-z]+", tok):
            tokens += [LATIN_NAMES[c] for c in tok]
        elif tok not in NUMBER_WORDS:
            tokens.append(tok)
    return " ".join(tokens)


def similarity(expected: str, heard: str) -> float:
    a, b = normalize(expected), normalize(heard)
    if not a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def strip_marks(text: str) -> str:
    return text.replace(ACUTE, "").replace("+", "")


def split_sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    parts = re.split(r"(?<=[.!?…])\s+", flat)
    return [p.strip() for p in parts if p.strip()]


def plus_to_acute(text: str) -> str:
    """'зам+ок' -> 'замо́к' (U+0301 after the vowel); drops marks on single-vowel words."""
    out: list[str] = []
    for token in re.split(r"(\s+)", text):
        if "+" not in token:
            out.append(token)
            continue
        vowels = sum(ch.lower() in VOWELS for ch in token)
        if vowels < 2:
            out.append(token.replace("+", ""))
            continue
        res: list[str] = []
        i = 0
        while i < len(token):
            c = token[i]
            if c == "+" and i + 1 < len(token) and token[i + 1].lower() in VOWELS:
                res.append(token[i + 1] + ACUTE)
                i += 2
            else:
                if c != "+":
                    res.append(c)
                i += 1
        out.append("".join(res))
    return "".join(out)


def expected_stress(plus_text: str) -> dict[str, int]:
    """word (lowercase, unmarked) -> stressed vowel index, for polysyllabic words."""
    exp: dict[str, int] = {}
    for token in re.findall(r"[а-яёА-ЯЁ+]+", plus_text):
        if "+" not in token:
            continue
        clean = token.replace("+", "").lower()
        if sum(ch in VOWELS for ch in clean) < 2:
            continue
        idx = 0
        for i, ch in enumerate(token):
            if ch == "+":
                idx = sum(c.lower() in VOWELS for c in token[:i].replace("+", ""))
                break
        exp[clean] = idx
    return exp


def romanize_word(word: str) -> str:
    return "".join(TRANS.get(c, "") for c in word)


def trim_silence(wav: np.ndarray, sr: int, thresh_db: float = -40.0, keep: float = 0.04) -> np.ndarray:
    amp = 10 ** (thresh_db / 20)
    idx = np.where(np.abs(wav) > amp)[0]
    if len(idx) == 0:
        return wav
    pad = int(sr * keep)
    return wav[max(0, idx[0] - pad): min(len(wav), idx[-1] + pad)]


# ---------- models ----------

class Accentuator:
    """ruaccent (Den4ikAI) is the stress dictionary. We do not invent + placement for Russian.

    Qwen3-TTS mangles common words if every word is marked (measured: sim 0.7 vs 1.0), so
    narration keeps U+0301 only on qwen_force_marks / custom_dict / run overrides. Reference
    text stays fully marked so the clone prompt still teaches the notation.
    """

    def __init__(self) -> None:
        from ruaccent import RUAccent

        custom = ruaccent_custom_dict()
        self.acc = RUAccent()
        self.acc.load(
            omograph_model_size="turbo3.1",
            use_dictionary=True,
            tiny_mode=False,
            custom_dict=custom,
        )
        self.force_overrides: dict[str, str] = dict(custom)
        for word in force_mark_words():
            if word in self.force_overrides:
                continue
            marked = self.acc.accents.get(word)
            if marked and "+" in marked:
                self.force_overrides[word] = marked

    def plus(self, text: str) -> str:
        return self.acc.process_all(text)

    def selective(self, text: str, overrides: dict[str, str], marks: str = "overrides") -> str:
        """marks: 'overrides' — Qwen problem words + ruaccent custom_dict; 'homographs' — also
        dictionary homographs and words unknown to ruaccent; 'none' — strip everything."""
        plus = self.plus(text)
        forced = dict(self.force_overrides)
        forced.update(overrides)
        plus = overlay_forced(plus, forced)
        forced_words = set(force_mark_words())
        forced_words |= {strip_marks(v).lower() for v in forced.values()} | {k.lower() for k in forced}
        out: list[str] = []
        for token in re.split(r"(\s+)", plus):
            if "+" not in token:
                out.append(token)
                continue
            core = re.sub(r"[^а-яёА-ЯЁ+]", "", token)
            clean = core.replace("+", "").lower()
            keep = clean in forced_words
            if marks == "homographs":
                keep = keep or clean in self.acc.omographs or clean not in self.acc.accents
            if marks == "none":
                keep = False
            out.append(token if keep else token.replace("+", ""))
        return "".join(out)


def overlay_forced(plus: str, forced: dict[str, str]) -> str:
    """Replace a token by its unmarked lemma so ruaccent's '+' does not block custom_dict."""
    by_clean = {k.lower(): v for k, v in forced.items()}
    out: list[str] = []
    for token in re.split(r"(\s+)", plus):
        core = re.sub(r"[^а-яёА-ЯЁ+]", "", token)
        form = by_clean.get(core.replace("+", "").lower())
        if form and core:
            token = token.replace(core, _cap_marked(core, form), 1)
        out.append(token)
    return "".join(out)


def _cap_marked(original_core: str, form: str) -> str:
    bare = original_core.replace("+", "")
    if not bare[:1].isupper():
        return form
    chars = list(form)
    for i, ch in enumerate(chars):
        if ch != "+":
            chars[i] = ch.upper()
            break
    return "".join(chars)


class Verifier:
    def __init__(self, model_name: str = "small") -> None:
        import whisper

        self.model = whisper.load_model(model_name)

    def heard(self, wav: np.ndarray, sr: int) -> str:
        import torch
        import torchaudio.functional as F
        import whisper

        audio = wav.astype(np.float32)
        if sr != 16000:
            audio = F.resample(torch.from_numpy(audio), sr, 16000).numpy()
        audio = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
        opts = whisper.DecodingOptions(language="ru", without_timestamps=True, fp16=False)
        return whisper.decode(self.model, mel, opts).text


class StressChecker:
    """MMS forced alignment → which vowel of each word carries duration+energy peak."""

    def __init__(self) -> None:
        import torch
        from torchaudio.pipelines import MMS_FA

        self.torch = torch
        self.model = MMS_FA.get_model().to("cuda").eval()
        self.dictionary = MMS_FA.get_dict(star=None)

    def check(self, wav: np.ndarray, sr: int, sentence: str, expected: dict[str, int]) -> tuple[list[dict], float]:
        import torchaudio.functional as F

        torch = self.torch
        words = re.findall(r"[а-яё]+", strip_marks(sentence).lower())
        roman = [romanize_word(w) for w in words]
        tokens = [self.dictionary[c] for w in roman for c in w if c in self.dictionary]
        if not tokens:
            return [], 1.0
        audio = torch.from_numpy(wav).float()
        if sr != 16000:
            audio = F.resample(audio, sr, 16000)
        with torch.inference_mode():
            emission, _ = self.model(audio.unsqueeze(0).to("cuda"))
        emission = emission[0].cpu()
        targets = torch.tensor([tokens], dtype=torch.int32)
        try:
            aligned, _ = F.forced_align(emission.unsqueeze(0), targets, blank=0)
        except Exception:  # noqa: BLE001 — audio shorter than tokens, etc.
            return [], 1.0
        spans = F.merge_tokens(aligned[0], torch.ones_like(aligned[0], dtype=torch.float32))
        ratio = audio.shape[0] / emission.shape[0]
        times = [(s.start * ratio / 16000, s.end * ratio / 16000) for s in spans]
        report: list[dict] = []
        pos = 0
        for word, rom in zip(words, roman):
            vowel_spans: list[tuple[float, float, float]] = []
            p = pos
            for ch in word:
                r = TRANS.get(ch, "")
                if not r:
                    continue
                if ch in VOWELS and p + len(r) - 1 < len(times):
                    s, e = times[p][0], times[p + len(r) - 1][1]
                    seg = audio[int(s * 16000): int(e * 16000)]
                    rms = float(seg.pow(2).mean().sqrt()) if seg.numel() else 0.0
                    vowel_spans.append((s, e, rms))
                p += len(r)
            pos += len(rom)
            want = expected.get(word)
            if want is None or len(vowel_spans) < 2:
                continue
            durs = np.array([e - s for s, e, _ in vowel_spans])
            rms = np.array([r for _, _, r in vowel_spans])
            score = durs / (durs.max() + 1e-9) + rms / (rms.max() + 1e-9)
            got = int(score.argmax())
            report.append({"word": word, "want": want, "got": got, "ok": got == want})
        acc = sum(r["ok"] for r in report) / len(report) if report else 1.0
        return report, acc


class Synth:
    def __init__(self, mode: str, ref_wav: Path | None = None, ref_text: str | None = None, instruct: str = "") -> None:
        import torch
        from qwen_tts import Qwen3TTSModel

        repo = {"clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"}[mode]
        self.mode = mode
        self.instruct = instruct
        self.model = Qwen3TTSModel.from_pretrained(repo, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa")
        self.prompt = None
        if mode == "clone":
            assert ref_wav is not None
            self.prompt = self.model.create_voice_clone_prompt(ref_audio=str(ref_wav), ref_text=ref_text)

    def take(self, text: str) -> tuple[np.ndarray, int]:
        if self.mode == "design":
            wavs, sr = self.model.generate_voice_design(text=text, language="Russian", instruct=self.instruct)
        else:
            wavs, sr = self.model.generate_voice_clone(
                text=text, language="Russian", voice_clone_prompt=self.prompt, non_streaming_mode=True
            )
        return np.asarray(wavs[0], dtype=np.float32), sr


# ---------- brand voice ----------

def design_reference(name: str, instruct: str, ref_text: str, tries: int, verifier: Verifier, acc: Accentuator) -> Path:
    """Create voices/<name>/ with the best VoiceDesign take of ref_text."""
    import soundfile as sf

    out = VOICES / name
    out.mkdir(parents=True, exist_ok=True)
    synth = Synth("design", instruct=instruct)
    letters = len(re.sub(r"[^а-яА-ЯёЁ]", "", ref_text))
    best: tuple[float, np.ndarray, int, dict] | None = None
    log: list[dict] = []
    for i in range(tries):
        wav, sr = synth.take(ref_text)
        wav = trim_silence(wav, sr)
        dur = len(wav) / sr
        heard = verifier.heard(wav, sr)
        sim = similarity(ref_text, heard)
        cps = letters / max(dur, 0.1)  # letters per second: pace
        score = sim * 2 + min(cps, 16) / 16
        row = {"take": i, "sim": round(sim, 3), "dur": round(dur, 2), "cps": round(cps, 1), "heard": heard.strip()}
        log.append(row)
        if sim >= 0.9 and (best is None or score > best[0]):
            best = (score, wav, sr, row)
    if best is None:
        raise SystemExit(f"voice design failed verification: {log}")
    sf.write(str(out / "ref.wav"), best[1], best[2])
    marked = plus_to_acute(acc.plus(ref_text))
    (out / "ref.txt").write_text(marked, encoding="utf-8")
    write_json(out / "meta.json", {"instruct": instruct, "ref_text": ref_text, "ref_text_marked": marked, "chosen": best[3], "takes": log, "model": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"})
    del synth
    return out


# ---------- narration ----------

@dataclass
class TakeLog:
    sentence: str
    attempt: int
    marked: bool
    heard: str
    sim: float
    dur: float
    max_dur: float
    stress_acc: float
    stress: list[dict] = field(default_factory=list)


def synthesize(
    text: str,
    voice_dir: Path,
    out_raw: Path,
    verifier: Verifier,
    acc: Accentuator,
    checker: StressChecker | None,
    gap: float,
    tries: int,
    min_sim: float,
    overrides: dict[str, str],
    marks: str = "overrides",
    marked_min_sim: float = 0.97,
    tts_latin: bool = True,
) -> dict:
    """Take policy (measured on narrator-ru):

    1. An unmarked take comes first — the model pronounces common words and known brands
       correctly on its own, and marks add an audible glide on the stressed vowel in ~1/3 of takes.
    2. Marks are used only for words ruaccent marked that are in qwen_force_marks / custom_dict
       or the run's stress-overrides.json; with --marks homographs, also for dictionary homographs.
       A marked take replaces the clean one only when Whisper hears it almost perfectly
       (sim ≥ marked_min_sim) and the forced-alignment stress check does not contradict it.
    3. Any take that Whisper cannot confirm (sim < min_sim) or that runs too long is regenerated.
    """
    import soundfile as sf

    ref_text = (voice_dir / "ref.txt").read_text(encoding="utf-8").strip()
    synth = Synth("clone", voice_dir / "ref.wav", ref_text)
    sentences = split_sentences(text)
    chunks: list[np.ndarray] = []
    sr = 24000
    log: list[TakeLog] = []
    doubtful: list[dict] = []
    marked_sentences: list[str] = []
    for sentence in sentences:
        plus = acc.selective(sentence, overrides, marks)
        marked_sentence = plus_to_acute(plus) if marks != "none" else sentence
        expected = expected_stress(plus) if marks != "none" else {}
        has_marks = ACUTE in marked_sentence
        if has_marks:
            marked_sentences.append(marked_sentence)
        letters = len(re.sub(r"[^а-яА-ЯёЁa-zA-Z]", "", sentence))
        max_dur = 0.11 * letters + 0.9
        best: tuple[float, np.ndarray, TakeLog] | None = None
        marked_words = set(expected)  # words that carry a mark in this sentence
        clean_sim = 0.0

        def words_heard_intact(heard: str) -> bool:
            """Every marked word must be heard exactly (kills 'Алибоюбы'-style glides)."""
            heard_norm = set(normalize(heard).split())
            return all(w.replace("ё", "е") in heard_norm for w in marked_words)

        def run_take(attempt: int, use_marks: bool) -> tuple[float, np.ndarray, TakeLog]:
            spoken = marked_sentence if use_marks else sentence
            if tts_latin:
                spoken = apply_latin_for_tts(spoken)
            wav, rate = synth.take(spoken)
            wav = trim_silence(wav, rate)
            dur = len(wav) / rate
            heard = verifier.heard(wav, rate)
            sim = similarity(sentence, heard)
            stress_report: list[dict] = []
            stress_acc = 1.0
            if checker is not None and expected and sim >= min_sim - 0.1:
                stress_report, stress_acc = checker.check(wav, rate, sentence, expected)
            ok_dur = dur <= max_dur
            if use_marks:
                # a marked take replaces the clean one only if Whisper hears it at least as well
                # AND every marked word is intact AND alignment does not contradict the stress
                eligible = ok_dur and sim >= max(marked_min_sim, clean_sim) and words_heard_intact(heard) and stress_acc >= 0.5
            else:
                eligible = ok_dur and sim >= min_sim
            score = sim + (0.02 if use_marks and eligible else 0.0) + (0.5 if eligible else 0.0) - (0.6 if not ok_dur else 0.0)
            entry = TakeLog(sentence, attempt, use_marks, heard.strip(), round(sim, 3), round(dur, 2), round(max_dur, 2), round(stress_acc, 3), stress_report)
            log.append(entry)
            return score, wav, entry

        plan: list[bool] = [False]  # clean take first
        if has_marks:
            plan.append(True)
        while len(plan) < tries:
            plan.append(False)
        for attempt, use_marks in enumerate(plan):
            score, wav, entry = run_take(attempt, use_marks)
            if not use_marks:
                clean_sim = max(clean_sim, entry.sim)
            if best is None or score > best[0]:
                best = (score, wav, entry)
            clean_ok = not use_marks and entry.sim >= min_sim and entry.dur <= max_dur
            if clean_ok and not has_marks:
                break
            if use_marks and score >= 0.5 + marked_min_sim:
                break
            if clean_ok and has_marks and attempt >= 1:
                break
        assert best is not None
        sr = 24000
        chunks.append(best[1])
        chunks.append(np.zeros(int(sr * gap), dtype=np.float32))
        doubtful += [r for r in best[2].stress if not r["ok"]]
    full = np.concatenate(chunks)
    out_raw.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_raw), full, sr)
    return {
        "sentences": len(sentences),
        "takes": [t.__dict__ for t in log],
        "doubtful_stress": doubtful,
        "marked_sentences": marked_sentences,
        "voice": str(voice_dir),
        "model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base (clone of VoiceDesign reference)",
    }


def tighten(raw: Path, out_wav: Path, out_mp3: Path, tempo: float) -> float:
    chain = f"atempo={tempo},loudnorm=I=-15:TP=-1.2:LRA=9,apad=pad_dur=0.35"
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", raw, "-af", chain, "-ar", "48000", out_wav], quiet=True)
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", out_wav, "-b:a", "192k", out_mp3], quiet=True)
    return ffprobe_duration(out_wav)


def align(wav_path: Path, words_path: Path, model_name: str = "small") -> dict:
    import whisper

    model = whisper.load_model(model_name)
    result = model.transcribe(str(wav_path), word_timestamps=True, language="ru")
    words = [
        {"text": str(w.get("word", "")).strip(), "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3)}
        for seg in result.get("segments", [])
        for w in seg.get("words", [])
    ]
    payload = {"text": result.get("text", ""), "words": words}
    write_json(words_path, payload)
    return payload


# ---------- CLI ----------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("design-voice", help="create/refresh a brand voice reference with VoiceDesign")
    d.add_argument("--name", default=DEFAULT_VOICE)
    d.add_argument("--instruct", default=DEFAULT_DESIGN)
    d.add_argument("--ref-text", default=DEFAULT_REF_TEXT)
    d.add_argument("--tries", type=int, default=6)

    n = sub.add_parser("narrate", help="script.txt -> assets/vo.mp3 + vo-words.json + voice-report.json")
    n.add_argument("--project", required=True, help="run directory (contains script.txt)")
    n.add_argument("--script", default="script.txt")
    n.add_argument("--voice", default=DEFAULT_VOICE)
    n.add_argument("--tempo", type=float, default=1.06)
    n.add_argument("--gap", type=float, default=0.12)
    n.add_argument("--tries", type=int, default=3)
    n.add_argument("--min-sim", type=float, default=0.74)
    n.add_argument("--no-stress-check", action="store_true")
    n.add_argument("--marks", choices=["overrides", "homographs", "none"], default="overrides", help="where to put U+0301 stress marks")
    n.add_argument("--marked-min-sim", type=float, default=0.97, help="Whisper similarity a marked take needs to replace the clean one")
    n.add_argument("--stress-overrides", default="stress-overrides.json", help="{word: 'w+ord'} in project dir")
    n.add_argument("--no-tts-latin", action="store_true", help="do not rewrite Cyrillic brand spellings to Latin for TTS")
    n.add_argument("--output-dir", default="", help="write vo.wav/mp3 here instead of <run>/assets (does not overwrite production)")
    n.add_argument("--skip-align", action="store_true", help="skip Whisper word timestamps")
    n.add_argument("--limit", type=int, default=0)

    args = ap.parse_args()
    if args.cmd == "design-voice":
        verifier = Verifier("small")
        acc = Accentuator()
        out = design_reference(args.name, args.instruct, args.ref_text, args.tries, verifier, acc)
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        say({"voice": str(out), "chosen": meta["chosen"]})
        return

    project = Path(args.project)
    assets = Path(args.output_dir) if args.output_dir else project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    text = (project / args.script).read_text(encoding="utf-8").strip()
    if args.limit:
        text = " ".join(split_sentences(text)[: args.limit])
    voice_dir = VOICES / args.voice
    if not (voice_dir / "ref.wav").exists():
        raise SystemExit(f"voice {args.voice} not found — run: python scripts/voice.py design-voice --name {args.voice}")
    overrides_path = project / args.stress_overrides
    run_overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}

    verifier = Verifier("small")
    acc = Accentuator()
    checker = None if (args.no_stress_check or args.marks == "none") else StressChecker()
    raw = assets / "vo-raw.wav"
    report = synthesize(
        text,
        voice_dir,
        raw,
        verifier,
        acc,
        checker,
        args.gap,
        args.tries,
        args.min_sim,
        run_overrides,
        args.marks,
        args.marked_min_sim,
        tts_latin=not args.no_tts_latin,
    )
    report["marks_mode"] = args.marks
    report["tts_latin"] = not args.no_tts_latin
    report["stress_override_keys"] = sorted({*acc.force_overrides, *run_overrides})
    del checker
    duration = tighten(raw, assets / "vo.wav", assets / "vo.mp3", args.tempo)
    report.update({"duration": round(duration, 2), "tempo": args.tempo})
    if not args.skip_align:
        words = align(assets / "vo.wav", assets / "vo-words.json")
        report["words"] = len(words["words"])
        (assets / "vo-duration.txt").write_text(f"{duration:.3f}", encoding="ascii")
    else:
        report["words"] = 0
        (assets / "vo-duration.txt").write_text(f"{duration:.3f}", encoding="ascii")
    write_json(assets / "voice-report.json" if args.output_dir else project / "voice-report.json", report)
    say({"duration": report["duration"], "words": report.get("words", 0), "sentences": report["sentences"], "doubtful_stress": len(report["doubtful_stress"]), "report": str((assets if args.output_dir else project) / "voice-report.json")})


if __name__ == "__main__":
    main()
