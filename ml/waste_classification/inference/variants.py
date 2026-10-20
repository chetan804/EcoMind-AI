"""Orientation variants used for training augmentation and test-time augmentation (TTA)."""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image

VARIANTS: dict[str, Callable[[Image.Image], Image.Image]] = {
    "identity": lambda im: im,
    "hflip": lambda im: im.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    "vflip": lambda im: im.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
    "rot90": lambda im: im.transpose(Image.Transpose.ROTATE_90),
}
