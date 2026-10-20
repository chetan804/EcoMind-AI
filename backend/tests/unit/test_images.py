"""Upload validation: hostile and malformed inputs must be rejected or neutralised."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.exceptions import UnsupportedMediaTypeError
from app.modules.waste_reports.images import InvalidImageError, normalize_image


def _encode(
    fmt: str, size: tuple[int, int] = (64, 48), mode: str = "RGB", **kwargs: object
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, (30, 140, 60) if mode == "RGB" else 0).save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("fmt", "content_type", "extension"),
    [("JPEG", "image/jpeg", "jpg"), ("PNG", "image/png", "png"), ("WEBP", "image/webp", "webp")],
)
def test_valid_images_are_accepted_and_described_from_their_real_content(
    fmt: str, content_type: str, extension: str
) -> None:
    result = normalize_image(_encode(fmt))
    assert (result.content_type, result.extension) == (content_type, extension)
    assert (result.width, result.height) == (64, 48)
    with Image.open(io.BytesIO(result.content)) as decoded:
        assert decoded.format == fmt


def test_exif_gps_metadata_is_stripped() -> None:
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    exif[0x8825] = {1: "N", 2: (17.0, 22.0, 30.0), 3: "E", 4: (78.0, 29.0, 0.0)}  # GPS IFD
    original = _encode("JPEG", exif=exif.tobytes())
    with Image.open(io.BytesIO(original)) as probe:
        assert probe.getexif().get_ifd(0x8825), "test setup: the source must carry GPS data"
    assert b"SecretCameraMaker" in original

    cleaned = normalize_image(original).content
    assert b"SecretCameraMaker" not in cleaned
    with Image.open(io.BytesIO(cleaned)) as decoded:
        assert not decoded.getexif()
        assert "exif" not in decoded.info


def test_exif_orientation_is_applied_before_metadata_is_dropped() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 270 CW to display: a 64x48 landscape becomes 48x64 portrait
    result = normalize_image(_encode("JPEG", (64, 48), exif=exif.tobytes()))
    assert (result.width, result.height) == (48, 64)


def test_data_appended_to_an_image_does_not_survive() -> None:
    payload = b"<script>alert(1)</script>MZ-executable-bytes"
    cleaned = normalize_image(_encode("PNG") + payload).content
    assert payload not in cleaned and b"<script>" not in cleaned


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not an image at all",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>",
        b"%PDF-1.7 fake",
        b"GIF89a" + b"\x00" * 40,
    ],
)
def test_non_images_are_rejected_with_415(data: bytes) -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        normalize_image(data)


def test_a_real_but_unsupported_format_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        normalize_image(_encode("GIF"))
    with pytest.raises(UnsupportedMediaTypeError):
        normalize_image(_encode("BMP"))


def test_truncated_image_is_rejected() -> None:
    data = _encode("PNG", (400, 400))
    with pytest.raises(UnsupportedMediaTypeError):
        normalize_image(data[: len(data) // 2])


def test_image_that_is_too_small_is_rejected() -> None:
    with pytest.raises(InvalidImageError, match="too small"):
        normalize_image(_encode("PNG", (8, 8)))


def test_decompression_bomb_is_rejected_before_pixels_are_decoded() -> None:
    # 8000 x 8000 = 64 Mpx of one colour compresses to a few KB but would need 64+ MB decoded.
    bomb = _encode("PNG", (8000, 8000), mode="L")
    assert len(bomb) < 200_000, "test setup: the file must be small on the wire"
    with pytest.raises(InvalidImageError, match="too many pixels"):
        normalize_image(bomb)


def test_palette_png_with_transparency_stays_png() -> None:
    buffer = io.BytesIO()
    Image.new("P", (40, 40), 1).save(buffer, format="PNG", transparency=0)
    result = normalize_image(buffer.getvalue())
    assert result.content_type == "image/png"


def test_cmyk_jpeg_is_converted_so_it_can_be_re_encoded() -> None:
    result = normalize_image(_encode("JPEG", mode="CMYK"))
    assert result.content_type == "image/jpeg"
