from pydantic import ValidationError
import pytest

from core.audit_contracts import AuditReport, DesignPrinciple, Finding, Severity, SeveritySummary


def make_valid_finding(finding_id="F001", confidence=90.0):
    return Finding(
        finding_id=finding_id,
        principle=DesignPrinciple.VISUAL_HIERARCHY,
        severity=Severity.HIGH,
        location="Primary CTA button in the bottom-right of the hero section",
        observation="The submit button and cancel button have identical visual weight and color.",
        user_impact="Users cannot identify the primary action, increasing friction.",
        recommendation="Increase submit button font weight to 600 and apply filled background.",
        confidence=confidence,
    )


def test_valid_finding():
    finding = make_valid_finding()
    assert finding.finding_id == "F001"
    assert finding.flagged_for_review is False


def test_confidence_below_60_model_accepts_value():
    finding = make_valid_finding(confidence=55.0)
    assert finding.confidence == 55.0


def test_location_without_spatial_keyword_raises():
    with pytest.raises(ValidationError):
        Finding(
            finding_id="F001",
            principle=DesignPrinciple.CONTRAST,
            severity=Severity.CRITICAL,
            location="Priority action area",
            observation="Text has low contrast against background.",
            user_impact="Users cannot read the text.",
            recommendation="Increase contrast ratio to meet WCAG AA.",
            confidence=90.0,
        )


@pytest.mark.parametrize(
    "location",
    [
        "Heading and body text",
        "Top navigation bar link",
        "Center content image",
        "Right table cell",
    ],
)
def test_location_accepts_common_ui_element_references(location):
    finding = Finding(
        finding_id="F001",
        principle=DesignPrinciple.VISUAL_HIERARCHY,
        severity=Severity.HIGH,
        location=location,
        observation="The submit button and cancel button have identical visual weight and color.",
        user_impact="Users cannot identify the primary action, increasing friction.",
        recommendation="Increase submit button font weight to 600 and apply filled background.",
        confidence=90.0,
    )
    assert finding.location == location


def test_audit_report_requires_minimum_three_findings():
    findings = [make_valid_finding(f"F00{i}") for i in range(1, 3)]
    with pytest.raises(ValidationError):
        AuditReport(
            report_id="RPT-TEST",
            image_filename="test.png",
            llm_model_used="test-model",
            findings=findings,
            summary=SeveritySummary(),
        )


def test_audit_report_valid_with_three_findings():
    findings = [make_valid_finding(f"F00{i}") for i in range(1, 4)]
    report = AuditReport(
        report_id="RPT-TEST",
        image_filename="test.png",
        llm_model_used="test-model",
        findings=findings,
        summary=SeveritySummary(total=3, high=3),
    )
    assert report.level == 1
    assert len(report.findings) == 3


def test_audit_report_records_observable_trace_and_attempts():
    findings = [make_valid_finding(f"F00{i}") for i in range(1, 4)]
    report = AuditReport(
        report_id="RPT-TEST",
        image_filename="test.png",
        llm_model_used="test-model",
        findings=findings,
        summary=SeveritySummary(total=3, high=3),
        decision_trace=["request_received", "llm_attempt_limit:1"],
        llm_attempts=1,
    )
    assert report.decision_trace[-1] == "llm_attempt_limit:1"
    assert report.llm_attempts == 1
