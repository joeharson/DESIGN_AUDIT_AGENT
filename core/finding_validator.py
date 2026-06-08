"""LLM response parsing, schema validation, and report summaries."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from core.audit_contracts import Finding, Severity, SeveritySummary


def strip_markdown_fences(raw: str) -> str:
    text = raw.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return fence_match.group(1).strip() if fence_match else text


def parse_llm_response(raw_response: str) -> dict[str, Any]:
    text = strip_markdown_fences(raw_response)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object.")
    if "findings" not in parsed or not isinstance(parsed["findings"], list):
        raise ValueError("LLM response must contain a findings list.")
    return parsed


def validate_findings(parsed_response: dict[str, Any]) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    errors: list[str] = []
    for index, raw in enumerate(parsed_response.get("findings", []), start=1):
        try:
            finding = Finding.model_validate(raw)
            finding.flagged_for_review = finding.confidence < 60
            findings.append(finding)
        except ValidationError as exc:
            errors.append(f"Finding {index}: {exc}")
    return findings, errors


def compute_summary(findings: list[Finding]) -> SeveritySummary:
    summary = SeveritySummary(total=len(findings))
    for finding in findings:
        if finding.severity == Severity.CRITICAL:
            summary.critical += 1
        elif finding.severity == Severity.HIGH:
            summary.high += 1
        elif finding.severity == Severity.MEDIUM:
            summary.medium += 1
        elif finding.severity == Severity.LOW:
            summary.low += 1
        elif finding.severity == Severity.INFO:
            summary.info += 1
        if finding.flagged_for_review:
            summary.flagged_for_review += 1
    return summary


def build_validation_error_summary(errors: list[str]) -> str:
    if not errors:
        return "No validation errors were captured, but the response was incomplete."
    return "\n".join(errors[:10])
