from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from core.regression_scan_contracts import AuthConfig, PageConfig, PageScanResult, ScanConfig, ScanReport


def _scan_config_dict():
    return {
        "target_url": "https://example.com",
        "pages": [
            {
                "page_id": "home",
                "url": "/",
                "name": "Home",
                "dynamic_selectors": [".timestamp"],
            },
            {
                "page_id": "settings",
                "url": "/settings",
                "name": "Settings",
                "dynamic_selectors": [".counter"],
            },
            {
                "page_id": "billing",
                "url": "/billing",
                "name": "Billing",
                "dynamic_selectors": [".token"],
            }
        ],
    }


def test_scan_config_validates_from_dict():
    config = ScanConfig.model_validate(_scan_config_dict())

    assert config.viewport_width == 1440
    assert config.pages[0].page_id == "home"


def test_scan_config_requires_three_pages():
    data = _scan_config_dict()
    data["pages"] = data["pages"][:2]

    with pytest.raises(ValidationError):
        ScanConfig.model_validate(data)


def test_page_config_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        PageConfig.model_validate({"page_id": "home"})


def test_scan_report_constructs_with_page_results():
    page_result = PageScanResult(
        page_id="home",
        page_url="https://example.com",
        baseline_exists=False,
    )
    report = ScanReport(
        scan_id="SCAN-20260607000000-ABCDEF12",
        config_file="config.json",
        target_url="https://example.com",
        scan_started_at=datetime.now(UTC),
        page_results=[page_result],
        overall_status="baseline_created",
        llm_model_used="test-model",
    )

    assert report.level == 3
    assert report.page_results[0].page_id == "home"


@pytest.mark.parametrize("status", ["pass", "regression", "error", "baseline_created"])
def test_scan_report_accepts_valid_overall_statuses(status):
    report = ScanReport(
        scan_id="SCAN-20260607000000-ABCDEF12",
        config_file="config.json",
        target_url="https://example.com",
        overall_status=status,
        llm_model_used="test-model",
    )

    assert report.overall_status == status


def test_scan_report_rejects_invalid_overall_status():
    with pytest.raises(ValidationError):
        ScanReport(
            scan_id="SCAN-20260607000000-ABCDEF12",
            config_file="config.json",
            target_url="https://example.com",
            overall_status="unknown",
            llm_model_used="test-model",
        )


def test_auth_config_requires_all_selector_fields():
    with pytest.raises(ValidationError):
        AuthConfig.model_validate({"login_url": "https://example.com/login"})
