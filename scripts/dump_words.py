"""Readable dump of vo-words.json → vo-words.txt (one word per line with timings)."""

from __future__ import annotations

import sys
from pathlib import Path

from common import read_json

src = Path(sys.argv[1])
words = read_json(src)["words"]
out = src.with_suffix(".txt")
out.write_text("\n".join(f"{w['start']:7.2f} {w['end']:7.2f}  {w['text']}" for w in words), encoding="utf-8")
print(out, len(words))
