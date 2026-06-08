import pytest

from core.finding_validator import parse_llm_response, strip_markdown_fences, validate_findings


def test_strip_markdown_json_fence():
    raw = '```json\n{"findings": []}\n```'
    assert strip_markdown_fences(raw) == '{"findings": []}'


def test_strip_plain_fence():
    raw = '```\n{"findings": []}\n```'
    assert strip_markdown_fences(raw) == '{"findings": []}'


def test_parse_valid_json():
    raw = '{"findings": [], "agent_notes": null}'
    result = parse_llm_response(raw)
    assert result["findings"] == []


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError):
        parse_llm_response("this is not json at all }{")


def test_validate_findings_empty_list():
    findings, errors = validate_findings({"findings": []})
    assert findings == []
    assert errors == []


def test_validate_findings_missing_location_spatial_keyword():
    raw = {
        "findings": [{
            "finding_id": "F001",
            "principle": "visual_hierarchy",
            "severity": "high",
            "location": "priority action area",
            "observation": "Two buttons have identical visual weight making priority unclear.",
            "user_impact": "Users cannot identify the primary action.",
            "recommendation": "Increase CTA font weight to 600 and apply filled background.",
            "confidence": 88.0,
        }]
    }
    findings, errors = validate_findings(raw)
    assert len(findings) == 0
    assert len(errors) == 1
