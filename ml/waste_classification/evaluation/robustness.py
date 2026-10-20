"""Synthetic perturbations for stress-testing the classifier.

These are *proxies* for real-world conditions (lighting, focus, compression, clutter), applied to
studio photographs. They show relative sensitivity; they are not a substitute for field data.
"""

from __future__ import annotations

import io
from collections.abc import Callable

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

Perturbation = Callable[[Image.Image, np.random.Generator], Image.Image]


def _jpeg(image: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")


def _replace_background(image: Image.Image, fill: Image.Image) -> Image.Image:
    """Replace near-white (studio background) pixels with ``fill``."""
    pixels = np.asarray(image)
    mask = (pixels > 215).all(axis=2)
    out = np.where(mask[..., None], np.asarray(fill.resize(image.size)), pixels)
    return Image.fromarray(out.astype(np.uint8))


def _noise(image: Image.Image, rng: np.random.Generator) -> Image.Image:
    noisy = np.asarray(image, dtype=np.float32) + rng.normal(0, 20, (image.height, image.width, 3))
    return Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8))


def _occlude(image: Image.Image, rng: np.random.Generator) -> Image.Image:
    """Grey square covering ~30% of the area, at a random position."""
    side_w, side_h = int(image.width * 0.55), int(image.height * 0.55)
    x = int(rng.integers(0, image.width - side_w + 1))
    y = int(rng.integers(0, image.height - side_h + 1))
    out = np.asarray(image).copy()
    out[y : y + side_h, x : x + side_w] = 128
    return Image.fromarray(out)


def _texture(image: Image.Image, rng: np.random.Generator) -> Image.Image:
    coarse = rng.integers(40, 220, (8, 8, 3)).astype(np.uint8)
    return _replace_background(
        image, Image.fromarray(coarse).resize(image.size, Image.Resampling.BICUBIC)
    )


PERTURBATIONS: dict[str, Perturbation] = {
    "dark (brightness x0.5)": lambda im, r: ImageEnhance.Brightness(im).enhance(0.5),
    "bright (brightness x1.6)": lambda im, r: ImageEnhance.Brightness(im).enhance(1.6),
    "low contrast (x0.5)": lambda im, r: ImageEnhance.Contrast(im).enhance(0.5),
    "blur (gaussian r=3)": lambda im, r: im.filter(ImageFilter.GaussianBlur(3)),
    "jpeg quality 15": lambda im, r: _jpeg(im, 15),
    "sensor noise (sigma 20)": _noise,
    "low resolution (48 px)": lambda im, r: im.resize((64, 48)).resize(im.size),
    "rotated 20 deg": lambda im, r: im.rotate(20, fillcolor=(255, 255, 255)),
    "occlusion (~30% area)": _occlude,
    "background: mid grey": lambda im, r: _replace_background(
        im, Image.new("RGB", (8, 8), (128,) * 3)
    ),
    "background: coloured texture": _texture,
}
