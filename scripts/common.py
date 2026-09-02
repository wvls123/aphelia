"""Shared paths and helpers for Aphelia scripts (plugin-root aware)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PLUGIN_ROOT / "templates"
VOICES = PLUGIN_ROOT / "voices"


def memory_root() -> Path:
    """Where runs live: <workspace>/aphelia-memory (env APHELIA_MEMORY overrides)."""
    env = os.environ.get("APHELIA_MEMORY")
    if env:
        return Path(env)
    cwd = Path.cwd()
    new = cwd / "aphelia-memory"
    old = cwd / "framepro-memory"
    if not new.exists() and old.exists():
        return old
    return new


def run_dir(slug: str) -> Path:
    return memory_root() / "runs" / slug


def sh(cmd: list[str], cwd: Path | None = None, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    if not quiet:
        print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, check=True, text=True, capture_output=quiet)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def npx_bin() -> str:
    for candidate in ("npx.cmd", "npx"):
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit("npx not found on PATH")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def say(payload: object) -> None:
    """Machine-readable one-line result for the calling agent."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
