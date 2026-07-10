#!/usr/bin/env python3
"""Convert a photo into terminal ASCII art for the profile card.

One-time local tool (needs Pillow). Produces assets/ascii-art.json, which
scripts/generate_profile.py embeds into the SVG. The photo itself is never
committed.

Usage:
    python3 scripts/ascii_from_photo.py PHOTO [--cols 46] [--mode color|mono]
                                               [--contrast 1.15] [--floor 26]
                                               [--out assets/ascii-art.json]

Modes:
    color  quantized, desaturated pixel colors (neofetch-photo look)
    mono   brightness mapped onto muted grays (most restrained)

Dark pixels become spaces, so the subject floats on the terminal background.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install Pillow")

# Sparse -> dense. Index by brightness after the floor cutoff.
RAMP = " .':-=+*x%@#"

# Muted tones for mono mode, darkest -> brightest.
MONO_TONES = ["#3d444d", "#6e7681", "#8b949e", "#b1bac4", "#d0d7de", "#e6edf3"]

# Restrained terminal palette for color mode (hue buckets, muted).
COLOR_PALETTE = [
    ("red", "#e5534b"),
    ("orange", "#d29922"),
    ("yellow", "#c9b458"),
    ("green", "#57ab5a"),
    ("cyan", "#5cb8c4"),
    ("blue", "#6cb6ff"),
    ("magenta", "#b083f0"),
]
GRAYS = MONO_TONES


def luminance(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def nearest_terminal_color(r: int, g: int, b: int) -> str:
    """Map a pixel to a muted terminal color, falling back to grays."""
    mx, mn = max(r, g, b), min(r, g, b)
    lum = luminance(r, g, b)
    sat = 0 if mx == 0 else (mx - mn) / mx
    if sat < 0.30:  # effectively gray — pick a tone by brightness
        idx = min(int(lum / 256 * len(GRAYS)), len(GRAYS) - 1)
        return GRAYS[idx]
    # Hue in degrees
    import colorsys

    h, _, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    deg = h * 360
    if deg < 5 or deg >= 340:
        return dict(COLOR_PALETTE)["red"]
    if deg < 48:        # skin tones land here, not in red
        return dict(COLOR_PALETTE)["orange"]
    if deg < 70:
        return dict(COLOR_PALETTE)["yellow"]
    if deg < 165:
        return dict(COLOR_PALETTE)["green"]
    if deg < 210:
        return dict(COLOR_PALETTE)["cyan"]
    if deg < 265:
        return dict(COLOR_PALETTE)["blue"]
    return dict(COLOR_PALETTE)["magenta"]


def convert(
    photo: Path,
    cols: int,
    mode: str,
    contrast: float,
    floor: int,
    brighten: float = 1.0,
) -> dict:
    img = Image.open(photo).convert("RGB")
    img = ImageOps.exif_transpose(img)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if brighten != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brighten)

    # Terminal cells are ~2x taller than wide; compensate.
    w, h = img.size
    rows = max(1, round(h * (cols / w) * 0.5))
    img = img.resize((cols, rows), Image.LANCZOS)

    px = img.load()
    lines = []
    for y in range(rows):
        runs: list[dict] = []
        for x in range(cols):
            r, g, b = px[x, y]
            lum = luminance(r, g, b)
            if lum <= floor:
                ch, color = " ", None
            else:
                t = (lum - floor) / (255 - floor)
                ch = RAMP[min(int(t * len(RAMP)), len(RAMP) - 1)]
                if ch == " ":
                    color = None
                elif mode == "color":
                    color = nearest_terminal_color(r, g, b)
                else:
                    color = MONO_TONES[
                        min(int(t * len(MONO_TONES)), len(MONO_TONES) - 1)
                    ]
            if runs and runs[-1]["c"] == color:
                runs[-1]["t"] += ch
            else:
                runs.append({"t": ch, "c": color})
        # Trim trailing spaces
        while runs and runs[-1]["c"] is None and runs[-1]["t"].strip() == "":
            runs.pop()
        lines.append(runs)

    # Drop fully blank leading/trailing rows
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    return {"cols": cols, "rows": len(lines), "mode": mode, "lines": lines}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo", type=Path)
    ap.add_argument("--cols", type=int, default=46)
    ap.add_argument("--mode", choices=["color", "mono"], default="color")
    ap.add_argument("--contrast", type=float, default=1.15)
    ap.add_argument("--brighten", type=float, default=1.0)
    ap.add_argument("--floor", type=int, default=26,
                    help="luminance below this becomes empty space")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "assets" / "ascii-art.json")
    args = ap.parse_args()

    art = convert(args.photo, args.cols, args.mode, args.contrast,
                  args.floor, args.brighten)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(art, separators=(",", ":")) + "\n")

    # Preview in the terminal
    for line in art["lines"]:
        print("".join(run["t"] for run in line))
    print(f"\nwrote {args.out}  ({art['cols']}x{art['rows']})")


if __name__ == "__main__":
    main()
