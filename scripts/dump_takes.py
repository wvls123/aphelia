"""Readable dump of voice-report.json (takes, similarity, stress doubts) → <run>/voice-report.txt."""

from __future__ import annotations

import sys
from pathlib import Path

from common import read_json

src = Path(sys.argv[1])
rep = read_json(src)
lines = [f"duration {rep.get('duration')}s, words {rep.get('words')}, sentences {rep.get('sentences')}, model {rep.get('model')}", ""]
for t in rep["takes"]:
    flag = "OK " if t["sim"] >= 0.74 and t["dur"] <= t["max_dur"] else "BAD"
    lines.append(f"[{flag}] #{t['attempt']} marks={int(t['marked'])} sim={t['sim']:.2f} dur={t['dur']:.2f}/{t['max_dur']:.2f} stress={t['stress_acc']:.2f}")
    lines.append(f"      say : {t['sentence']}")
    lines.append(f"      hear: {t['heard']}")
if rep.get("doubtful_stress"):
    lines += ["", "doubtful stress (word: expected vowel# -> heard vowel#):"]
    lines += [f"  {d['word']}: {d['want']} -> {d['got']}" for d in rep["doubtful_stress"]]
out = src.with_suffix(".txt")
out.write_text("\n".join(lines), encoding="utf-8")
print(out)
