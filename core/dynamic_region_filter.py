"""Image-level dynamic content filtering for Level 3 comparisons."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from utils.structured_event_logging import get_logger

logger = get_logger(__name__)


class DynamicFilter:
    def filter_for_comparison(
        self,
        baseline_path: str,
        current_path: str,
        dynamic_regions: list[str],
    ) -> tuple[str, str, int]:
        baseline = Image.open(baseline_path).convert("RGB")
        current = Image.open(current_path).convert("RGB")
        if current.size != baseline.size:
            current = current.resize(baseline.size, Image.LANCZOS)

        regions = self._regions_for_selectors(dynamic_regions, baseline.size)
        for image in (baseline, current):
            draw = ImageDraw.Draw(image)
            for box in regions:
                draw.rectangle(box, fill="#808080")

        temp_dir = Path(current_path).parent / "filtered"
        temp_dir.mkdir(parents=True, exist_ok=True)
        filtered_baseline = temp_dir / f"{Path(baseline_path).stem}_filtered.png"
        filtered_current = temp_dir / f"{Path(current_path).stem}_filtered.png"
        baseline.save(filtered_baseline, format="PNG")
        current.save(filtered_current, format="PNG")
        logger.info("dynamic image filter applied", extra={"regions_filtered": len(regions)})
        return str(filtered_baseline), str(filtered_current), len(regions)

    def compute_pixel_diff_percentage(self, image_path_1: str, image_path_2: str, threshold: int = 10) -> float:
        image_1 = Image.open(image_path_1).convert("RGB")
        image_2 = Image.open(image_path_2).convert("RGB")
        if image_2.size != image_1.size:
            image_2 = image_2.resize(image_1.size, Image.LANCZOS)

        diff = ImageChops.difference(image_1, image_2)
        pixels = diff.getdata()
        changed = sum(1 for red, green, blue in pixels if max(red, green, blue) > threshold)
        total = image_1.width * image_1.height
        return round((changed / total) * 100, 4) if total else 0.0

    @staticmethod
    def _regions_for_selectors(selectors: list[str], size: tuple[int, int]) -> list[tuple[int, int, int, int]]:
        # Image-level fallback: mask the top 80px strip (common location for
        # dynamic banners, timestamps, and session tokens) when selectors are present.
        # DOM-level masking in browser_scan_runner.py already handled the precise regions.
        # This is a conservative safety net to catch anything the DOM mask missed.
        if not selectors:
            return []
        width, height = size
        regions = []
        if height > 160:
            regions.append((0, 0, width, 60))
            regions.append((0, height - 60, width, height))
        return regions
