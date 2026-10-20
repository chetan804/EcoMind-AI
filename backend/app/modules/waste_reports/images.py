"""Validation and normalisation of uploaded images.

The client's ``Content-Type`` and file name are never trusted. The bytes are decoded with Pillow,
the *detected* format must be JPEG, PNG or WebP, and the pixels are re-encoded into a fresh file.
Re-encoding is deliberate:

* it drops EXIF/XMP/ICC metadata, in particular GPS coordinates embedded by phone cameras (a
  citizen reporting waste near their home should not leak their location through the photo);
* it removes trailing data and polyglot payloads that a pure header check would let through;
* it applies the EXIF orientation first, so the stored pixels are upright.

Only the first frame of an animated image is kept. The decoded size is capped before any pixel
data is loaded, which blocks decompression bombs.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import AppError, UnsupportedMediaTypeError
from app.modules.waste_reports.constants import MAX_IMAGE_PIXELS, MIN_IMAGE_SIDE_PX

# PIL format name -> (content type, storage extension)
_FORMATS: dict[str, tuple[str, str]] = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


class InvalidImageError(AppError):
    status_code = 422
    code = "invalid_image"


@dataclass(frozen=True)
class NormalizedImage:
    content: bytes
    content_type: str
    extension: str
    width: int
    height: int


def normalize_image(data: bytes) -> NormalizedImage:
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = image.format or ""
            if fmt not in _FORMATS:
                raise UnsupportedMediaTypeError("Only JPEG, PNG and WebP images are accepted")
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise InvalidImageError("The image has too many pixels")
            if min(width, height) < MIN_IMAGE_SIDE_PX:
                raise InvalidImageError(
                    f"The image is too small (each side must be at least {MIN_IMAGE_SIDE_PX} px)"
                )
            image.seek(0)
            image.load()  # fully decodes: truncated or corrupt files fail here
            upright = ImageOps.exif_transpose(image)
            out_format = fmt
            if out_format == "JPEG" and upright.mode not in ("RGB", "L"):
                upright = upright.convert("RGB")
            buffer = io.BytesIO()
            save_args: dict[str, object] = {}
            if out_format == "JPEG":
                save_args = {"quality": 90, "optimize": True}
            elif out_format == "WEBP":
                save_args = {"quality": 90}
            upright.save(buffer, format=out_format, **save_args)  # no exif/icc passed: stripped
            out_w, out_h = upright.size
    except (UnsupportedMediaTypeError, InvalidImageError):
        raise
    except Image.DecompressionBombError as exc:
        raise InvalidImageError("The image has too many pixels") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError) as exc:
        # Not an image, or a damaged one. The decoder's message can quote file internals.
        raise UnsupportedMediaTypeError("The file is not a valid JPEG, PNG or WebP image") from exc
    content_type, extension = _FORMATS[fmt]
    return NormalizedImage(
        content=buffer.getvalue(),
        content_type=content_type,
        extension=extension,
        width=out_w,
        height=out_h,
    )
