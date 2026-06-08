"""Level 3 schemas for autonomous UI regression scans."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from core.comparison_audit_contracts import DiffReport


VALID_SCAN_STATUSES = {"pass", "regression", "error", "baseline_created"}


class AuthConfig(BaseModel):
    login_url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    success_indicator: str
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def resolve_env_reference(cls, value: str) -> str:
        if value.startswith("env:"):
            env_name = value[4:]
            resolved = os.getenv(env_name)
            if not resolved:
                raise ValueError(f"Environment variable {env_name} is required for authentication.")
            return resolved
        if value.isupper() and "_" in value:
            resolved = os.getenv(value)
            if not resolved:
                raise ValueError(f"Environment variable {value} is required for authentication.")
            return resolved
        return value


class PageConfig(BaseModel):
    page_id: str
    url: str
    name: str
    dynamic_selectors: list[str] = Field(default_factory=list)
    scroll_to_top: bool = True
    wait_for_selector: Optional[str] = None


class ScanConfig(BaseModel):
    target_url: str
    auth: Optional[AuthConfig] = None
    pages: list[PageConfig] = Field(..., min_length=3)
    viewport_width: int = Field(default=1440, ge=320, le=3840)
    viewport_height: int = Field(default=900, ge=320, le=2160)
    wait_after_navigation_ms: int = Field(default=2000, ge=0, le=10000)
    baseline_dir: str = "output/baselines"
    scan_output_dir: str = "output/scans"


class PageScanResult(BaseModel):
    page_id: str
    page_url: str
    page_title: str = ""
    screenshot_path: str = ""
    baseline_exists: bool
    baseline_screenshot_path: Optional[str] = None
    comparison_report: Optional[DiffReport] = None
    dynamic_regions_filtered: int = 0
    pixel_diff_percentage: Optional[float] = None
    scan_duration_seconds: float = 0.0
    error: Optional[str] = None
    decision_trace: list[str] = Field(default_factory=list)


class ScanReport(BaseModel):
    scan_id: str
    level: int = 3
    config_file: str
    target_url: str
    scan_started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scan_completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    pages_scanned: int = 0
    pages_with_regressions: int = 0
    pages_with_errors: int = 0
    page_results: list[PageScanResult] = Field(default_factory=list)
    overall_status: str
    llm_model_used: str
    decision_trace: list[str] = Field(default_factory=list)
    json_report_path: Optional[str] = None
    html_report_path: Optional[str] = None

    @field_validator("overall_status")
    @classmethod
    def valid_overall_status(cls, value: str) -> str:
        if value not in VALID_SCAN_STATUSES:
            raise ValueError(f"overall_status must be one of {sorted(VALID_SCAN_STATUSES)}.")
        return value


class ScanResponse(BaseModel):
    success: bool
    report: Optional[ScanReport] = None
    error: Optional[str] = None
    error_detail: Optional[str] = None


class BaselineInfo(BaseModel):
    page_id: str
    page_url: str
    baseline_path: str
    created_at: datetime
    size_bytes: int = 0
