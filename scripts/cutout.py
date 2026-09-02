"""Turn generated line-art PNGs into transparent cutouts (stickers), never "pictures in a square".

Alpha = max(ink mask, rembg saliency mask). The ink mask keeps every thin black stroke (rembg tends
to eat thin lines), rembg keeps white interior fills so the sticker stays opaque over coloured shapes.
Result is trimmed to its bounding box with a small padding.

Usage (agent-friendly):
    python scripts/cutout.py --project <run>            # every PNG in <run>/assets/raw → <run>/assets/cut
    python scripts/cutout.py --src a.png --dst cut/a.png
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import remove

from common import read_json, say, write_json


def ink_alpha(rgb: np.ndarray) -> np.ndarray:
    lum = rgb.min(axis=2).astype(np.float32)
    a = np.clip((235.0 - lum) / (235.0 - 120.0), 0.0, 1.0) * 255.0
    return a.astype(np.uint8)


def cutout(src: Path, dst: Path, pad: int = 24, use_rembg: bool = True) -> dict:
    img = Image.open(src).convert("RGB")
    rgb = np.asarray(img)
    alpha = ink_alpha(rgb)
    if use_rembg:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        out = Image.open(io.BytesIO(remove(buf.getvalue()))).convert("RGBA")
        alpha = np.maximum(alpha, np.asarray(out)[:, :, 3])
    rgba = np.dstack([rgb, alpha])
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        raise SystemExit(f"empty cutout: {src}")
    x0, x1 = max(0, xs.min() - pad), min(rgb.shape[1], xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(rgb.shape[0], ys.max() + pad)
    crop = Image.fromarray(rgba[y0:y1, x0:x1], "RGBA")
    dst.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dst, optimize=True)
    transparent = float((alpha < 8).mean())
    return {"src": str(src), "dst": str(dst), "w": crop.width, "h": crop.height, "transparent_ratio": round(transparent, 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="run dir: converts assets/raw/*.png → assets/cut/*.png")
    ap.add_argument("--src")
    ap.add_argument("--dst")
    ap.add_argument("--no-rembg", action="store_true")
    ap.add_argument("--force", action="store_true", help="redo cutouts that already exist")
    args = ap.parse_args()
    report: list[dict] = []
    if args.project:
        project = Path(args.project)
        raw = project / "assets" / "raw"
        for src in sorted(raw.glob("*.png")):
            dst = project / "assets" / "cut" / src.name
            if dst.exists() and not args.force and dst.stat().st_mtime >= src.stat().st_mtime:
                continue
            report.append(cutout(src, dst, use_rembg=not args.no_rembg))
        # parallel illustrators run this concurrently: merge into the existing report by file name
        report_path = project / "assets" / "cutout-report.json"
        merged: dict[str, dict] = {}
        if report_path.exists():
            for r in read_json(report_path):
                merged[Path(r["dst"]).name] = r
        for r in report:
            merged[Path(r["dst"]).name] = r
        write_json(report_path, sorted(merged.values(), key=lambda r: r["dst"]))
    else:
        if not (args.src and args.dst):
            raise SystemExit("--project or --src/--dst required")
        report.append(cutout(Path(args.src), Path(args.dst), use_rembg=not args.no_rembg))
    say({"cutouts": [{"file": Path(r["dst"]).name, "w": r["w"], "h": r["h"], "transparent": r["transparent_ratio"]} for r in report]})


if __name__ == "__main__":
    main()
