from pathlib import Path

from PIL import Image

from core.dynamic_region_filter import DynamicFilter


def _image(path: Path, color: str, size: tuple[int, int] = (100, 100)) -> str:
    Image.new("RGB", size, color=color).save(path, format="PNG")
    return str(path)


def test_pixel_diff_is_zero_for_identical_images(tmp_path):
    first = _image(tmp_path / "first.png", "white")
    second = _image(tmp_path / "second.png", "white")

    assert DynamicFilter().compute_pixel_diff_percentage(first, second) == 0.0


def test_pixel_diff_is_nonzero_for_different_images(tmp_path):
    first = _image(tmp_path / "first.png", "white")
    second = _image(tmp_path / "second.png", "black")

    assert DynamicFilter().compute_pixel_diff_percentage(first, second) > 0


def test_filter_for_comparison_returns_filtered_copies(tmp_path):
    baseline = _image(tmp_path / "baseline.png", "white", size=(200, 240))
    current = _image(tmp_path / "current.png", "black", size=(200, 240))

    filtered_baseline, filtered_current, count = DynamicFilter().filter_for_comparison(
        baseline,
        current,
        [".timestamp", ".counter"],
    )

    assert filtered_baseline != baseline
    assert filtered_current != current
    assert Path(filtered_baseline).exists()
    assert Path(filtered_current).exists()
    assert count == 2


def test_regions_for_selectors_uses_conservative_strips():
    regions = DynamicFilter._regions_for_selectors([".timestamp"], (200, 240))

    assert regions == [(0, 0, 200, 60), (0, 180, 200, 240)]
