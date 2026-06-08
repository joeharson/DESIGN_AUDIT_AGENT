"""Level 2 schemas for before/after design diff analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from core.audit_contracts import ChangeDirection, DesignPrinciple, Severity


class AccessibilityRegressionType(str, Enum):
    CONTRAST_DROP = "contrast_drop"
    FONT_SIZE_REDUCTION = "font_size_reduction"
    SPACING_COMPRESSION = "spacing_compression"
    TAP_TARGET_REDUCTION = "tap_target_reduction"
    NONE = "none"


class ComparisonFinding(BaseModel):
    finding_id: str = Field(..., description="Unique ID, for example CF001.")
    principle: DesignPrinciple
    change_direction: ChangeDirection
    severity: Severity
    location: str = Field(..., min_length=10)
    baseline_description: str = Field(..., min_length=15)
    current_description: str = Field(..., min_length=15)
    change_summary: str = Field(..., min_length=20)
    ux_impact: str = Field(..., min_length=15)
    reasoning: str = Field(..., min_length=20)
    confidence: float = Field(..., ge=0.0, le=100.0)
    flagged_for_review: bool = False
    accessibility_regression: AccessibilityRegressionType = AccessibilityRegressionType.NONE
    hex_values: Optional[dict[str, str]] = None
    pixel_measurements: Optional[dict[str, str]] = None

    @field_validator("hex_values", "pixel_measurements", mode="before")
    @classmethod
    def empty_measurement_dict_becomes_none(cls, value):
        if not value:
            return None
        if not isinstance(value, dict):
            return value
        cleaned = {key: str(item) for key, item in value.items() if item is not None and str(item).strip()}
        return cleaned or None

    @field_validator("location")
    @classmethod
    def location_must_reference_ui_or_position(cls, value: str) -> str:
        keywords = [
            "top", "bottom", "left", "right", "center", "middle",
            "upper", "lower", "inner", "outer", "above", "below",
            "beside", "adjacent", "between", "within", "inside",
            "header", "footer", "nav", "navbar", "navigation",
            "button", "cta", "link", "anchor", "tab", "tabs",
            "section", "hero", "banner", "card", "modal", "dialog",
            "form", "input", "field", "label", "placeholder",
            "icon", "image", "logo", "avatar", "thumbnail",
            "table", "row", "column", "cell", "grid",
            "list", "item", "menu", "dropdown", "sidebar",
            "panel", "drawer", "toolbar", "breadcrumb", "pagination",
            "badge", "chip", "tag", "tooltip", "popover",
            "heading", "title", "subtitle", "text", "body",
            "content", "copy", "caption", "description", "paragraph",
            "divider", "separator", "border", "container", "wrapper",
            "overlay", "backdrop", "carousel", "slider", "progress",
            "checkbox", "radio", "toggle", "switch", "select",
            "search", "filter", "sort", "action", "control",
            "page", "screen", "layout", "overall", "design",
            "background", "surface", "viewport", "canvas",
            "area", "region", "zone", "space", "scheme", "color",
            "colour", "typography", "font",
        ]
        if not any(keyword in value.lower() for keyword in keywords):
            raise ValueError("Location must contain a spatial reference or UI element name.")
        return value

    @model_validator(mode="after")
    def enforce_quality_guardrails(self) -> "ComparisonFinding":
        if self.confidence < 60.0:
            self.flagged_for_review = True
        reasoning_lower = self.reasoning.lower()
        subjective_markers = ("subjective", "preference", "aesthetic")
        objective_markers = (
            "contrast", "wcag", "accessibility", "font size", "spacing",
            "tap target", "alignment", "harder", "reduced", "decreased",
            "compression", "unreadable", "illegible",
        )
        has_subjective_marker = any(marker in reasoning_lower for marker in subjective_markers)
        has_objective_marker = any(marker in reasoning_lower for marker in objective_markers)
        if (
            self.change_direction == ChangeDirection.REGRESSION
            and has_subjective_marker
            and not has_objective_marker
            and self.accessibility_regression == AccessibilityRegressionType.NONE
        ):
            self.change_direction = ChangeDirection.NEUTRAL
            self.severity = Severity.INFO
            self.flagged_for_review = True
        if self.change_direction == ChangeDirection.NEUTRAL and self.severity != Severity.INFO:
            self.severity = Severity.INFO
        if self.accessibility_regression != AccessibilityRegressionType.NONE and self.change_direction != ChangeDirection.REGRESSION:
            self.change_direction = ChangeDirection.REGRESSION
            if self.severity == Severity.INFO:
                self.severity = Severity.HIGH
        return self


class OverallVerdict(BaseModel):
    net_result: ChangeDirection
    improvement_count: int = 0
    regression_count: int = 0
    neutral_count: int = 0
    accessibility_regressions_count: int = 0
    summary: str = Field(..., min_length=30)
    recommendation: str = Field(..., min_length=20)


class DiffReport(BaseModel):
    report_id: str
    level: int = 2
    baseline_filename: str
    current_filename: str
    baseline_resolution: Optional[str] = None
    current_resolution: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    llm_model_used: str
    processing_time_seconds: Optional[float] = None
    findings: list[ComparisonFinding] = Field(..., min_length=3)
    verdict: OverallVerdict
    agent_notes: Optional[str] = None
    decision_trace: list[str] = Field(default_factory=list)
    llm_attempts: int = Field(default=1, ge=0)
    json_report_path: Optional[str] = None
    html_report_path: Optional[str] = None


class CompareResponse(BaseModel):
    success: bool
    report: Optional[DiffReport] = None
    error: Optional[str] = None
    error_detail: Optional[str] = None
