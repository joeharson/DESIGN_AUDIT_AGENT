"""Image loading, validation, resizing, and base64 encoding."""

from __future__ import annotations

import base64
import io

from PIL import Image

from utils.structured_event_logging import get_logger

logger = get_logger(__name__)

SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_DIMENSION = 4096
MIN_DIMENSION = 100


def load_and_validate_image(
    file_bytes: bytes,
    filename: str,
    max_size_mb: float = 10.0,
) -> tuple[Image.Image, dict]:
    size_mb = len(file_bytes) / (1024 * 1024)
    logger.info(
        "Image received for validation",
        extra={"image_filename": filename, "size_mb": round(size_mb, 2)},
    )
    if size_mb > max_size_mb:
        raise ValueError(f"Image size {size_mb:.1f}MB exceeds maximum allowed {max_size_mb}MB.")

    try:
        image = Image.open(io.BytesIO(file_bytes))
        image.verify()
        image = Image.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Cannot open image '{filename}': {exc}") from exc

    if image.format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format '{image.format}'. Supported: {sorted(SUPPORTED_FORMATS)}.")

    width, height = image.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise ValueError(
            f"Image too small ({width}x{height}px). Minimum dimension is {MIN_DIMENSION}px."
        )

    metadata = {
        "image_filename": filename,
        "filename": filename,
        "format": image.format,
        "resolution": f"{width}x{height}",
        "size_mb": round(size_mb, 2),
        "mode": image.mode,
    }
    log_metadata = {key: value for key, value in metadata.items() if key != "filename"}
    logger.info("Image validated successfully", extra=log_metadata)
    return image, metadata


def resize_if_needed(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width <= MAX_DIMENSION and height <= MAX_DIMENSION:
        return image
    ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
    resized = image.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
    logger.info("Image resized to fit API limits", extra={"original": f"{width}x{height}", "new": f"{resized.width}x{resized.height}"})
    return resized


def encode_image_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    buffer = io.BytesIO()
    save_format = "JPEG" if fmt == "JPG" else fmt
    if save_format == "JPEG" and image.mode in {"RGBA", "P"}:
        image = image.convert("RGB")
    image.save(buffer, format=save_format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
