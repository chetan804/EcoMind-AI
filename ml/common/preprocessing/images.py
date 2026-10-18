"""Image preprocessing shared by every image-based model (training and inference must use it).

Keeping one implementation guarantees the pixels a model sees at inference time are prepared
exactly as they were during training. Per-model sizes come from ``ml/configs``.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

# Decompression-bomb guard: reject images with more pixels than this before decoding fully.
MAX_PIXELS = 50_000_000
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class InvalidImageError(ValueError):
    """The bytes are not a supported, safely decodable image."""


def load_rgb_image(data: bytes) -> Image.Image:
    """Decode bytes into an upright RGB image, validating format and size."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise InvalidImageError(f"Unsupported image format: {image.format}")
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise InvalidImageError("Image has too many pixels")
            image.load()
            upright = ImageOps.exif_transpose(image)  # honour camera orientation
            return upright.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Data is not a readable image") from exc


def resize_to_square(image: Image.Image, size: int) -> Image.Image:
    """Resize to ``size`` x ``size`` without distortion: scale the short side, centre-crop."""
    if size < 1:
        raise ValueError("size must be positive")
    return ImageOps.fit(image, (size, size), method=Image.Resampling.BILINEAR)


def prepare_image(data: bytes, size: int) -> Image.Image:
    """Full pipeline: decode, validate, orient, convert to RGB, resize to a square."""
    return resize_to_square(load_rgb_image(data), size)
