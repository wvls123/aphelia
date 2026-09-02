"""Merge assets/assets-*.json written by parallel illustrators into assets/assets.json (+ fill sizes from cut/)."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from common import read_json, say, write_json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    assets = Path(args.project) / "assets"
    merged: dict[str, dict] = {}
    if (assets / "assets.json").exists():
        for item in read_json(assets / "assets.json"):
            merged[item["name"]] = item
    for part in sorted(assets.glob("assets-*.json")):
        for item in read_json(part):
            merged[item["name"]] = item
    # every cutout on disk gets an entry even if an illustrator forgot to list it
    for png in sorted((assets / "cut").glob("*.png")):
        with Image.open(png) as im:
            w, h = im.size
        item = merged.setdefault(png.stem, {"name": png.stem, "kind": "char" if png.stem.startswith("char-") else "ill", "description": "", "reusable": True})
        item["w"], item["h"] = w, h
        item["src"] = f"cut/{png.name}"
    missing = [n for n in merged if not (assets / "cut" / f"{n}.png").exists()]
    for n in missing:
        merged.pop(n)
    out = sorted(merged.values(), key=lambda x: x["name"])
    write_json(assets / "assets.json", out)
    say({"assets": len(out), "missing_cutouts_dropped": missing, "file": str(assets / "assets.json")})


if __name__ == "__main__":
    main()
