"""Side-by-side and difference images for the authenticated screens (developer tooling).

Reads out/<id>@auth-light.png (from capture-auth.mjs) and the matching reference crop, downscales the
render to the reference's own size (never enlarges the reference), ignores the 3 px frame, and writes
out/<id>@auth-sidebyside.png, out/<id>@auth-diff.png and out/auth-metrics.json.
The reference crops are blurry and include captions and neighbouring screens, so SSIM is a rough
guide to layout and colour only.  Usage: python compare-auth.py [targetId ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from skimage.metrics import structural_similarity

here = Path(__file__).parent
root = here.parents[2]
cfg = json.loads((here / "auth-targets.json").read_text())
inset = cfg["frameInset"]
out = here / "out"
wanted = set(sys.argv[1:])
metrics = {}
for t in cfg["targets"]:
    if wanted and t["id"] not in wanted:
        continue
    ref = Image.open(root / "docs/ui/reference" / t["reference"]).convert("RGB")
    rw, rh = ref.size
    inner = ref.crop((inset, inset, rw - inset, rh - inset))
    mine = Image.open(out / f"{t['id']}@auth-{t.get('theme', 'light')}.png").convert("RGB").resize(inner.size, Image.Resampling.LANCZOS)
    blur = lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32)  # noqa: E731
    a, b = blur(inner), blur(mine)
    ssim = float(structural_similarity(a, b, channel_axis=2, data_range=255))
    mae = float(np.abs(a - b).mean())
    metrics[t["id"]] = {"reference": t["reference"], "ssim": round(ssim, 3), "mean_abs_colour_error": round(mae, 1)}
    side = Image.new("RGB", (inner.width * 2 + 8, inner.height), (40, 40, 40))
    side.paste(inner, (0, 0))
    side.paste(mine, (inner.width + 8, 0))
    side.resize((side.width * 3, side.height * 3), Image.Resampling.NEAREST).save(out / f"{t['id']}@auth-sidebyside.png")
    diff = np.abs(a - b).mean(axis=2)
    Image.fromarray(np.clip(diff * 3, 0, 255).astype(np.uint8)).resize((inner.width * 3, inner.height * 3)).save(out / f"{t['id']}@auth-diff.png")
    print(f"{t['id']:<16} SSIM {ssim:.3f}  colour error {mae:.1f}/255")
(out / "auth-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
