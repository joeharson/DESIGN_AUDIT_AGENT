import pytest
from pydantic import ValidationError

from core.audit_contracts import ChangeDirection, DesignPrinciple, Severity
from core.comparison_audit_contracts import (
    AccessibilityRegressionType,
    ComparisonFinding,
    DiffReport,
    OverallVerdict,
)


def make_finding(fid="CF001", confidence=88.0, accessibility="none"):
    return ComparisonFinding(
        finding_id=fid,
        principle=DesignPrinciple.CONTRAST,
        change_direction=ChangeDirection.REGRESSION,
        severity=Severity.HIGH,
        location="Center hero primary button",
        baseline_description="Dark blue button with white text and strong contrast.",
        current_description="Light gray button with white text and weaker contrast.",
        change_summary="Button background changed from dark blue to light gray, reducing label contrast.",
        ux_impact="The primary action is harder for low-vision users to identify.",
        reasoning="This is a regression because the visible contrast is lower in the current screenshot.",
        confidence=confidence,
        accessibility_regression=accessibility,
    )


def make_verdict():
    return OverallVerdict(
        net_result=ChangeDirection.REGRESSION,
        improvement_count=1,
        regression_count=3,
        neutral_count=1,
        accessibility_regressions_count=1,
        summary="The update is a net regression because usability and accessibility issues increased.",
        recommendation="Revert the contrast regression before shipping the current version.",
    )


def test_valid_comparison_finding():
    finding = make_finding()
    assert finding.finding_id == "CF001"
    assert finding.flagged_for_review is False


def test_low_confidence_flags_for_review():
    finding = make_finding(confidence=55.0)
    assert finding.flagged_for_review is True


def test_accessibility_regression_type():
    finding = make_finding(accessibility="contrast_drop")
    assert finding.accessibility_regression == AccessibilityRegressionType.CONTRAST_DROP


def test_empty_measurement_dicts_become_none():
    finding = ComparisonFinding.model_validate(
        {
            **make_finding().model_dump(),
            "hex_values": {},
            "pixel_measurements": {},
        }
    )
    assert finding.hex_values is None
    assert finding.pixel_measurements is None


def test_measurement_dicts_drop_none_values():
    finding = ComparisonFinding.model_validate(
        {
            **make_finding().model_dump(),
            "hex_values": {"baseline_label": None, "current_label": "#ffffff"},
        }
    )
    assert finding.hex_values == {"current_label": "#ffffff"}


def test_subjective_only_regression_is_normalized_to_neutral_review():
    finding = ComparisonFinding.model_validate(
        {
            **make_finding().model_dump(),
            "reasoning": "This is subjective and mostly a preference change.",
            "accessibility_regression": "none",
        }
    )
    assert finding.change_direction == ChangeDirection.NEUTRAL
    assert finding.severity == Severity.INFO
    assert finding.flagged_for_review is True


def test_neutral_change_severity_is_normalized_to_info():
    finding = ComparisonFinding.model_validate(
        {
            **make_finding().model_dump(),
            "change_direction": "neutral",
            "severity": "high",
        }
    )
    assert finding.severity == Severity.INFO


def test_location_accepts_global_visual_system_terms():
    finding = make_finding()
    finding = ComparisonFinding.model_validate(
        {
            **finding.model_dump(),
            "location": "Color scheme and typography",
        }
    )
    assert finding.location == "Color scheme and typography"


def test_location_without_ui_or_position_raises():
    with pytest.raises(ValidationError):
        ComparisonFinding(
            finding_id="CF001",
            principle=DesignPrinciple.CONTRAST,
            change_direction=ChangeDirection.REGRESSION,
            severity=Severity.HIGH,
            location="somewhere vague",
            baseline_description="Dark blue button with white text.",
            current_description="Light gray button with white text.",
            change_summary="Button contrast visibly decreased between screenshots.",
            ux_impact="The button is harder to read.",
            reasoning="Contrast decreased, making this an objective regression.",
            confidence=88.0,
        )


def test_diff_report_accepts_three_or_more_findings():
    findings = [make_finding(f"CF00{i}") for i in range(1, 4)]
    report = DiffReport(
        report_id="DIFF-TEST",
        baseline_filename="before.png",
        current_filename="after.png",
        llm_model_used="fake-model",
        findings=findings,
        verdict=make_verdict(),
    )
    assert report.level == 2
    assert len(report.findings) == 3
