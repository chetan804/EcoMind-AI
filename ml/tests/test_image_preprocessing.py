import io

import pytest
from PIL import Image

from ml.common.preprocessing.images import (
    InvalidImageError,
    load_rgb_image,
    prepare_image,
    resize_to_square,
)


def encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def test_converts_any_mode_to_rgb() -> None:
    rgba = Image.new("RGBA", (10, 8), (255, 0, 0, 128))
    assert load_rgb_image(encode(rgba)).mode == "RGB"
    assert load_rgb_image(encode(Image.new("L", (4, 4), 90))).mode == "RGB"


def test_prepare_returns_requested_square_without_distortion() -> None:
    wide = Image.new("RGB", (200, 100), (0, 0, 0))
    wide.paste((255, 255, 255), (50, 0, 150, 100))  # white centre, black sides
    result = prepare_image(encode(wide), 64)
    assert result.size == (64, 64)
    assert result.getpixel((32, 32)) == (255, 255, 255)  # centre crop kept the centre
    assert result.getpixel((3, 32)) == (255, 255, 255)  # sides were cropped, not squeezed


def test_exif_orientation_is_applied() -> None:
    image = Image.new("RGB", (20, 10), (0, 0, 255))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    assert load_rgb_image(buffer.getvalue()).size == (10, 20)


def test_non_image_bytes_rejected() -> None:
    with pytest.raises(InvalidImageError):
        load_rgb_image(b"definitely not an image")


def test_unsupported_format_rejected() -> None:
    with pytest.raises(InvalidImageError, match="Unsupported"):
        load_rgb_image(encode(Image.new("RGB", (4, 4)), "BMP"))


def test_oversized_pixel_count_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ml.common.preprocessing.images.MAX_PIXELS", 50)
    with pytest.raises(InvalidImageError, match="too many pixels"):
        load_rgb_image(encode(Image.new("RGB", (10, 10))))


def test_resize_rejects_invalid_size() -> None:
    with pytest.raises(ValueError):
        resize_to_square(Image.new("RGB", (4, 4)), 0)


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_damaged_exif_block_is_ignored_not_fatal(fmt: str) -> None:
    """Regression: a PNG/WebP whose EXIF block is not a TIFF structure made Pillow raise
    SyntaxError from exif_transpose. Orientation is then unknown; pixels are used as stored."""
    buffer = io.BytesIO()
    Image.new("RGB", (30, 20), (9, 9, 9)).save(
        buffer, fmt, exif=b"\x00\x08\x00\x04\x01\x1a\x00\x05"
    )
    assert load_rgb_image(buffer.getvalue()).size == (30, 20)
