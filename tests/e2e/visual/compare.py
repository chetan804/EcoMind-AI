"""Compare a rendered screen with its reference crop (developer tooling).

Method: the screenshot is downscaled to the reference's own pixel size (the reference is never
enlarged), the reference's showcase-frame border is excluded, and both are compared by
  * landmark geometry (DOM boxes converted to reference pixels vs boxes read from the reference),
  * structural similarity and mean colour error on a lightly blurred copy,
  * a coarse colour grid.
The references are small, blurry and AI-generated, so these numbers guide iteration only.

Usage: python compare.py [targetId ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from skimage.metrics import structural_similarity

here = Path(__file__).parent
root = here.parents[2]
cfg = json.loads((here / "targets.json").read_text())
inset = cfg["frameInset"]
out = here / "out"
wanted = set(sys.argv[1:])
EDGE_NAMES = ["left", "top", "right", "bottom"]


def blur(im):
    return im.filter(ImageFilter.GaussianBlur(0.8))


for t in cfg["targets"]:
    if wanted and t["id"] not in wanted:
        continue
    shot = out / f"{t['id']}@ref.png"
    meta = json.loads((out / f"{t['id']}@ref.json").read_text())
    ref = Image.open(root / t["reference"]).convert("RGB")
    rw, rh = ref.size
    inner = ref.crop((inset, inset, rw - inset, rh - inset))
    mine = Image.open(shot).convert("RGB").resize(inner.size, Image.Resampling.LANCZOS)
    a, b = np.asarray(blur(inner), dtype=np.float32), np.asarray(blur(mine), dtype=np.float32)
    ssim = structural_similarity(a, b, channel_axis=2, data_range=255)
    mae = float(np.abs(a - b).mean())
    scale = meta["scale"]

    print(f"\n== {t['id']}  (viewport {meta['width']}x{meta['height']}, scale {scale:.4f}, horizontal overflow {meta['horizontalOverflowPx']}px)")
    print(f"   SSIM {ssim:.3f}   mean abs colour error {mae:.1f}/255")

    # coarse colour grid (6x4), mean RGB distance
    gw, gh = 6, 4
    ga = np.asarray(inner.resize((gw, gh), Image.Resampling.BOX), dtype=np.float32)
    gb = np.asarray(mine.resize((gw, gh), Image.Resampling.BOX), dtype=np.float32)
    worst = np.linalg.norm(ga - gb, axis=2)
    print(f"   colour grid: mean {worst.mean():.1f}, worst cell {worst.max():.1f} (RGB distance)")

    print("   landmark deltas, in design px (positive = mine is larger / further right or down):")
    for lm in t["landmarks"]:
        box = meta["rects"].get(lm["name"])
        if not box:
            print(f"     {lm['name']:<26} NOT FOUND ({lm['selector']})")
            continue
        mine_ref = [inset + box[0] * scale, inset + box[1] * scale, inset + box[2] * scale, inset + box[3] * scale]
        edges = lm.get("edges") or ["left", "top", "right", "bottom"]
        parts = []
        for i, nme in enumerate(EDGE_NAMES):
            if nme in edges:
                parts.append(f"{nme[0].upper()} {(mine_ref[i] - lm['ref'][i]) / scale:+6.0f}")
        if "width" in edges:
            parts.append(f"W {((mine_ref[2]-mine_ref[0]) - (lm['ref'][2]-lm['ref'][0])) / scale:+6.0f}")
        print(f"     {lm['name']:<26} " + "  ".join(parts))

    side = Image.new("RGB", (inner.width * 2 + 8, inner.height), (40, 40, 40))
    side.paste(inner, (0, 0))
    side.paste(mine, (inner.width + 8, 0))
    side = side.resize((side.width * 3, side.height * 3), Image.Resampling.NEAREST)
    side.save(out / f"{t['id']}@sidebyside.png")
    diff = np.abs(a - b).mean(axis=2)
    heat = Image.fromarray(np.clip(diff * 3, 0, 255).astype(np.uint8)).resize((inner.width * 3, inner.height * 3))
    heat.save(out / f"{t['id']}@diff.png")
