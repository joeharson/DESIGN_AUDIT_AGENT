import io

import pytest
from PIL import Image

from utils.screenshot_image_processing import encode_image_to_base64, load_and_validate_image


def make_test_image_bytes(width=800, height=600, fmt="PNG") -> bytes:
    image = Image.new("RGB", (width, height), color=(100, 150, 200))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def test_valid_png_image():
    img_bytes = make_test_image_bytes()
    image, metadata = load_and_validate_image(img_bytes, "test.png")
    assert image.size == (800, 600)
    assert metadata["format"] == "PNG"
    assert metadata["resolution"] == "800x600"


def test_image_too_small_raises():
    img_bytes = make_test_image_bytes(width=50, height=50)
    with pytest.raises(ValueError, match="too small"):
        load_and_validate_image(img_bytes, "tiny.png")


def test_encode_returns_string():
    img_bytes = make_test_image_bytes()
    image, _ = load_and_validate_image(img_bytes, "test.png")
    encoded = encode_image_to_base64(image)
    assert isinstance(encoded, str)
    assert len(encoded) > 100
