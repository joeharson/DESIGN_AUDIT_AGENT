"""
Shared Pydantic models for the Design Audit Agent.
Level 2 and Level 3 should extend these contracts without renaming fields.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DesignPrinciple(str, Enum):
    VISUAL_HIERARCHY = "visual_hierarchy"
    CONTRAST = "contrast_wcag_aa"
    SPACING = "spacing"
    ALIGNMENT = "alignment"
    CONSISTENCY = "consistency"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ChangeDirection(str, Enum):
    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    NEUTRAL = "neutral"


class Finding(BaseModel):
    finding_id: str = Field(..., description="Unique finding id, for example F001.")
    principle: DesignPrinciple
    severity: Severity
    location: str = Field(..., min_length=10)
    observation: str = Field(..., min_length=20)
    user_impact: str = Field(..., min_length=15)
    recommendation: str = Field(..., min_length=20)
    confidence: float = Field(..., ge=0.0, le=100.0)
    flagged_for_review: bool = False

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, value: float) -> float:
        return round(value, 1)

    @field_validator("location")
    @classmethod
    def location_must_be_spatial(cls, value: str) -> str:
        spatial_keywords = [
            "top", "bottom", "left", "right", "center", "middle", "header",
            "footer", "nav", "button", "section", "above", "below", "corner",
            "sidebar", "hero", "card", "modal", "form", "input", "label",
            "heading", "text", "body", "content", "link", "image", "icon",
            "list", "table", "row", "column", "cell",
        ]
        if not any(keyword in value.lower() for keyword in spatial_keywords):
            raise ValueError(
                "Location must contain a spatial reference or UI element name."
            )
        return value


class SeveritySummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    total: int = 0
    flagged_for_review: int = 0


class AuditReport(BaseModel):
    report_id: str
    level: int = 1
    image_filename: str
    image_resolution: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    llm_model_used: str
    processing_time_seconds: Optional[float] = None
    findings: list[Finding] = Field(..., min_length=1)
    summary: SeveritySummary = Field(default_factory=SeveritySummary)
    agent_notes: Optional[str] = None
    decision_trace: list[str] = Field(
        default_factory=list,
        description="Observable execution trace: guardrail decisions, attempts, and validation status.",
    )
    llm_attempts: int = Field(default=1, ge=0, description="Number of LLM calls made for this report.")
    json_report_path: Optional[str] = None
    html_report_path: Optional[str] = None

    @field_validator("findings")
    @classmethod
    def minimum_three_findings(cls, value: list[Finding]) -> list[Finding]:
        if len(value) < 3:
            raise ValueError(
                f"A valid audit report requires at least 3 distinct findings. Got {len(value)}."
            )
        return value


class AnalyzeResponse(BaseModel):
    success: bool
    report: Optional[AuditReport] = None
    error: Optional[str] = None
    error_detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_provider: str
    llm_model: str
