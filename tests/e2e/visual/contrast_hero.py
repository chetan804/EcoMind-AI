"""Step 2 of the hero contrast check (see contrast-hero.mjs).

For every text box on the landing hero, take the brightest 5% of artwork pixels beneath it and
compute the WCAG contrast ratio against the text colour. WCAG AA needs 4.5:1 (3:1 for large text).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).parent / "out"


def lin(c):
    c = c / 255.0
    return np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lum(rgb):
    r, g, b = lin(rgb[..., 0]), lin(rgb[..., 1]), lin(rgb[..., 2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


failures = 0
for text_file in sorted(OUT.glob("hero-text-*.json"), key=lambda p: -int(re.findall(r"\d+", p.name)[0])):
    width = int(re.findall(r"\d+", text_file.name)[0])
    img = np.asarray(Image.open(OUT / f"hero-bg-{width}.png").convert("RGB")).astype(float)
    worst = (99.0, "", 0)
    for item in json.loads(text_file.read_text()):
        if item["bg"] != "rgba(0, 0, 0, 0)":
            continue  # elements with their own fill are covered by the token contrast tests
        x0, y0 = max(0, int(item["x"])), max(0, int(item["y"]))
        x1, y1 = min(img.shape[1], int(item["x"] + item["w"]) + 1), min(img.shape[0], int(item["y"] + item["h"]) + 1)
        patch = img[y0:y1, x0:x1]
        if patch.size == 0:
            continue
        bg = float(np.quantile(lum(patch), 0.95))
        tr, tg, tb = (float(v) for v in re.findall(r"[\d.]+", item["color"])[:3])
        t = float(lum(np.array([tr, tg, tb])))
        ratio = (max(bg, t) + 0.05) / (min(bg, t) + 0.05)
        if ratio < worst[0]:
            worst = (ratio, item["name"], item["size"])
    large = worst[2] >= 24
    ok = worst[0] >= (3.0 if large else 4.5)
    failures += not ok
    print(f"{width:>5}px  worst {worst[0]:5.2f}:1  {'ok  ' if ok else 'FAIL'} ({worst[1]!r}, {worst[2]:.0f}px)")
sys.exit(1 if failures else 0)
