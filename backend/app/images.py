"""Validate uploaded photos and normalize them before they go to a detector."""

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Guards against decompression bombs: a small file that expands to a huge bitmap.
MAX_PIXELS = 50_000_000
JPEG_QUALITY = 85


class InvalidImageError(ValueError):
    """The upload is not an image we can process. The message is safe to show to users."""


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    width: int
    height: int
    sha256: str
    media_type: str = "image/jpeg"


def prepare_image(raw: bytes, max_edge: int) -> PreparedImage:
    """Return the photo upright, flattened to RGB, shrunk to fit max_edge and re-encoded as JPEG.

    Re-encoding also drops EXIF metadata, which can include the GPS location of the photo.
    """
    if not raw:
        raise InvalidImageError("The upload is empty.")

    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise InvalidImageError("Upload a JPEG, PNG or WebP image.")
            if img.width * img.height > MAX_PIXELS:
                raise InvalidImageError("The image resolution is too high.")

            img = ImageOps.exif_transpose(img)
            img = _flatten_to_rgb(img)
            img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

            out = io.BytesIO()
            img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
            width, height = img.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise InvalidImageError("The file is not a readable image.") from exc

    return PreparedImage(
        data=out.getvalue(),
        width=width,
        height=height,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")
