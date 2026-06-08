"""Prompt helpers for Level 3 autonomous regression scans."""

from __future__ import annotations


def build_regression_context_prompt(
    page_name: str,
    page_url: str,
    pixel_diff_percentage: float,
    dynamic_regions_filtered: int,
) -> str:
    """
    User-turn prompt for Level 3 autonomous regression analysis.
    Reuses SYSTEM_PROMPT_L2 as system prompt — no new system prompt needed.
    This user prompt sets the Level 3 context so the model understands
    it is comparing the same page across two points in time, not two
    deliberately different design versions.
    """

    if pixel_diff_percentage < 2.0:
        finding_guidance = (
            "The pixel diff is small (under 2%). Report only findings you can clearly observe "
            "in the screenshots. If the images look nearly identical, return 1-3 findings maximum "
            "focused on any visible change. Do not invent findings to reach a minimum count."
        )
        minimum_note = "Minimum 1 finding if any visible change exists. Return an empty findings list only if the pages are visually identical."
    elif pixel_diff_percentage < 10.0:
        finding_guidance = (
            "The pixel diff is moderate. Focus on real layout, color, or typography changes. "
            "Do not flag rendering differences caused by font antialiasing, sub-pixel shifts, "
            "or JPEG compression artifacts — these are not regressions."
        )
        minimum_note = "Minimum 3 findings covering the most significant visible changes."
    else:
        finding_guidance = (
            "The pixel diff is significant, indicating a real visual change. "
            "Report all observable regressions and improvements across all five principles."
        )
        minimum_note = "Minimum 5 findings covering all five design principles."

    return "\n".join([
        "This is a Level 3 autonomous UI regression scan.",
        f"Page: {page_name}",
        f"URL: {page_url}",
        f"Pixel diff vs stored baseline: {pixel_diff_percentage:.4f}%",
        f"Dynamic regions masked before comparison: {dynamic_regions_filtered}",
        "",
        "IMPORTANT CONTEXT FOR THIS SCAN TYPE:",
        "You are comparing the SAME PAGE captured at two different points in time.",
        "IMAGE 1 is the STORED BASELINE — the previously approved state of this page.",
        "IMAGE 2 is the CURRENT SCREENSHOT — the live state of this page today.",
        "Most visual differences are either genuine regressions (a developer changed something "
        "that broke the design) or genuine improvements (a developer fixed something).",
        "Dynamic content — timestamps, session tokens, user counters, loading spinners, "
        "flash messages — has already been masked with grey rectangles before this comparison. "
        "Do not flag grey masked regions as regressions.",
        "Do not flag sub-pixel rendering differences, font hinting variation, or "
        "image compression artifacts as regressions.",
        "",
        finding_guidance,
        "",
        "For every finding, populate pixel_measurements with:",
        f"  page_pixel_diff_percentage: {pixel_diff_percentage:.4f}%",
        "  affected_region: describe the region of the page where the change is visible",
        f"  dynamic_regions_filtered_before_analysis: {dynamic_regions_filtered}",
        "",
        minimum_note,
        "Use the Level 2 JSON schema exactly. Return only valid JSON with no markdown or code fences.",
    ])