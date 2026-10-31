import hashlib
import io

import pytest
from PIL import Image

from app import images
from app.images import InvalidImageError, prepare_image
from tests.conftest import make_image


def open_result(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_large_image_is_shrunk_to_max_edge_keeping_aspect_ratio():
    prepared = prepare_image(make_image(4000, 3000), max_edge=1568)

    assert (prepared.width, prepared.height) == (1568, 1176)
    assert open_result(prepared.data).size == (1568, 1176)


def test_small_image_is_not_upscaled():
    prepared = prepare_image(make_image(300, 200), max_edge=1568)

    assert (prepared.width, prepared.height) == (300, 200)


def test_output_is_rgb_jpeg_even_for_transparent_png():
    prepared = prepare_image(make_image(100, 100, fmt="PNG", mode="RGBA"), max_edge=1568)

    result = open_result(prepared.data)
    assert result.format == "JPEG"
    assert result.mode == "RGB"
    assert prepared.media_type == "image/jpeg"


def test_webp_is_accepted():
    prepared = prepare_image(make_image(100, 100, fmt="WEBP"), max_edge=1568)

    assert open_result(prepared.data).format == "JPEG"


def test_exif_orientation_is_applied_and_metadata_is_stripped():
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90° clockwise to display
    exif[0x010F] = "PhoneMaker"  # Make
    raw = make_image(200, 100, exif=exif)

    prepared = prepare_image(raw, max_edge=1568)

    assert (prepared.width, prepared.height) == (100, 200)
    assert len(open_result(prepared.data).getexif()) == 0


def test_sha256_is_of_the_original_upload():
    raw = make_image()

    assert prepare_image(raw, max_edge=1568).sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"", "empty"),
        (b"definitely not an image", "not a readable image"),
        (make_image(50, 50, fmt="GIF", mode="P"), "JPEG, PNG or WebP"),
    ],
)
def test_bad_uploads_are_rejected(raw, message):
    with pytest.raises(InvalidImageError, match=message):
        prepare_image(raw, max_edge=1568)


def test_truncated_image_is_rejected():
    raw = make_image(400, 400)

    with pytest.raises(InvalidImageError, match="not a readable image"):
        prepare_image(raw[: len(raw) // 2], max_edge=1568)


def test_huge_resolution_is_rejected(monkeypatch):
    monkeypatch.setattr(images, "MAX_PIXELS", 10_000)

    with pytest.raises(InvalidImageError, match="resolution is too high"):
        prepare_image(make_image(200, 100), max_edge=1568)
