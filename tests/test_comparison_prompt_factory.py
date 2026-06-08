from core.comparison_prompt_factory import SYSTEM_PROMPT_L2, build_comparison_prompt, build_l2_correction_prompt


def test_l2_system_prompt_mentions_required_outputs():
    assert "at least 5 visible differences" in SYSTEM_PROMPT_L2
    assert "accessibility_regression" in SYSTEM_PROMPT_L2
    assert "verdict" in SYSTEM_PROMPT_L2


def test_build_comparison_prompt_labels_images():
    prompt = build_comparison_prompt(
        {"resolution": "800x600", "format": "PNG"},
        {"resolution": "800x600", "format": "WEBP"},
    )
    assert "BASELINE" in prompt
    assert "CURRENT" in prompt
    assert "at least 5" in prompt


def test_l2_prompt_enforces_baseline_to_current_direction():
    prompt = build_comparison_prompt()
    assert "BASELINE -> CURRENT" in prompt
    assert "fixed in CURRENT" in prompt
    assert "improvement, not regression" in prompt
    assert "Regression direction must be based on CURRENT compared with BASELINE" in SYSTEM_PROMPT_L2


def test_l2_prompt_mentions_background_surface_wcag_checks():
    prompt = build_comparison_prompt(
        {"resolution": "800x600", "format": "PNG"},
        {"resolution": "800x600", "format": "WEBP"},
    )
    assert "page backgrounds" in prompt
    assert "surfaces" in prompt
    assert "not only login/sign-in controls" in prompt
    assert "page background" in SYSTEM_PROMPT_L2
    assert "card surface" in SYSTEM_PROMPT_L2


def test_l2_correction_prompt_requires_five_findings():
    prompt = build_l2_correction_prompt("Only 4 valid findings.")
    assert "at least 5 findings" in prompt
    assert "Only 4 valid findings." in prompt
