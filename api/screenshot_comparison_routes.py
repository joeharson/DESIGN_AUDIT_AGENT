"""FastAPI routes for Level 2 before/after comparison."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, File, UploadFile
from pydantic import ValidationError

from core.retry_guardrails import get_max_l2_llm_attempts
from core.comparison_prompt_factory import SYSTEM_PROMPT_L2, build_comparison_prompt, build_l2_correction_prompt
from core.audit_report_writer import save_diff_report_html, save_diff_report_json
from core.audit_contracts import ChangeDirection
from core.comparison_audit_contracts import (
    AccessibilityRegressionType,
    CompareResponse,
    ComparisonFinding,
    DiffReport,
    OverallVerdict,
)
from core.finding_validator import build_validation_error_summary, parse_llm_response
from utils.screenshot_image_processing import encode_image_to_base64, load_and_validate_image, resize_if_needed
from utils.structured_event_logging import get_logger

MIN_COMPARISON_FINDINGS = 5

logger = get_logger(__name__)
router_l2 = APIRouter()
_llm_client = None


def set_llm_client_l2(client) -> None:
    global _llm_client
    _llm_client = client


def _validate_comparison_response(parsed: dict[str, Any]) -> tuple[list[ComparisonFinding], OverallVerdict, list[str]]:
    findings: list[ComparisonFinding] = []
    errors: list[str] = []
    for index, raw in enumerate(parsed.get("findings", []), start=1):
        try:
            findings.append(ComparisonFinding.model_validate(raw))
        except ValidationError as exc:
            errors.append(f"Finding {index}: {exc}")

    try:
        verdict = OverallVerdict.model_validate(parsed.get("verdict"))
    except ValidationError as exc:
        verdict = _compute_verdict(findings)
        errors.append(f"Verdict: {exc}")

    return findings, verdict, errors


def _compute_verdict(findings: list[ComparisonFinding]) -> OverallVerdict:
    improvement_count = sum(1 for f in findings if f.change_direction == ChangeDirection.IMPROVEMENT)
    regression_count = sum(1 for f in findings if f.change_direction == ChangeDirection.REGRESSION)
    neutral_count = sum(1 for f in findings if f.change_direction == ChangeDirection.NEUTRAL)
    a11y_count = sum(1 for f in findings if f.accessibility_regression != AccessibilityRegressionType.NONE)
    if regression_count > improvement_count:
        net_result = ChangeDirection.REGRESSION
    elif improvement_count > regression_count:
        net_result = ChangeDirection.IMPROVEMENT
    else:
        net_result = ChangeDirection.NEUTRAL
    return OverallVerdict(
        net_result=net_result,
        improvement_count=improvement_count,
        regression_count=regression_count,
        neutral_count=neutral_count,
        accessibility_regressions_count=a11y_count,
        summary=(
            f"Detected {improvement_count} improvements, {regression_count} regressions, "
            f"and {neutral_count} neutral changes across the compared screenshots."
        ),
        recommendation="Review all regressions before shipping, especially any accessibility regressions.",
    )


@router_l2.post("/compare", response_model=CompareResponse)
async def compare_screenshots(
    baseline: UploadFile = File(..., description="Baseline before screenshot."),
    current: UploadFile = File(..., description="Current after screenshot."),
) -> CompareResponse:
    try:
        request_id = uuid.uuid4().hex[:8].upper()
        start_time = time.time()
        decision_trace = ["compare_request_received"]
        validation_error_summary = ""
        llm_attempts = 0

        if _llm_client is None:
            return CompareResponse(
                success=False,
                error="LLM client not initialized",
                error_detail="Restart the server after setting GROQ_API_KEY in .env.",
            )

        try:
            max_size_mb = float(os.getenv("MAX_IMAGE_SIZE_MB", "10"))
            baseline_bytes = await baseline.read()
            current_bytes = await current.read()
            baseline_image, baseline_meta = load_and_validate_image(
                baseline_bytes, baseline.filename or "baseline", max_size_mb=max_size_mb
            )
            current_image, current_meta = load_and_validate_image(
                current_bytes, current.filename or "current", max_size_mb=max_size_mb
            )
            decision_trace.append(f"baseline_validated:{baseline_meta.get('resolution')}:{baseline_meta.get('format')}")
            decision_trace.append(f"current_validated:{current_meta.get('resolution')}:{current_meta.get('format')}")
        except ValueError as exc:
            return CompareResponse(success=False, error="Image validation failed", error_detail=str(exc))

        try:
            baseline_image = resize_if_needed(baseline_image)
            current_image = resize_if_needed(current_image)
            baseline_b64 = encode_image_to_base64(baseline_image, fmt=baseline_meta["format"])
            current_b64 = encode_image_to_base64(current_image, fmt=current_meta["format"])
            user_prompt = build_comparison_prompt(baseline_meta, current_meta)
            decision_trace.append("both_images_encoded")
        except Exception as exc:
            logger.exception("Comparison image preparation failed", extra={"request_id": request_id})
            return CompareResponse(success=False, error="Image preparation failed", error_detail=str(exc))

        validated_findings: list[ComparisonFinding] = []
        verdict: OverallVerdict | None = None
        agent_notes = None
        max_attempts = get_max_l2_llm_attempts()
        decision_trace.append(f"llm_attempt_limit:{max_attempts}")

        for attempt in range(1, max_attempts + 1):
            try:
                prompt = user_prompt if attempt == 1 else build_l2_correction_prompt(validation_error_summary)
                llm_attempts += 1
                decision_trace.append(f"llm_call_started:{attempt}")
                raw_response = _llm_client.analyze_two_images(
                    system_prompt=SYSTEM_PROMPT_L2,
                    user_prompt=prompt,
                    image_base64_1=baseline_b64,
                    image_format_1=baseline_meta["format"],
                    image_base64_2=current_b64,
                    image_format_2=current_meta["format"],
                )
                decision_trace.append(f"llm_call_completed:{attempt}")
            except Exception as exc:
                logger.exception("Level 2 LLM call failed", extra={"request_id": request_id, "attempt": attempt})
                return CompareResponse(success=False, error="LLM service unavailable", error_detail=str(exc))

            try:
                parsed = parse_llm_response(raw_response)
                agent_notes = parsed.get("agent_notes")
                validated_findings, verdict, validation_errors = _validate_comparison_response(parsed)
                decision_trace.append(f"validation_completed:{len(validated_findings)}_valid_findings")
                if len(validated_findings) >= MIN_COMPARISON_FINDINGS:
                    break
                validation_error_summary = build_validation_error_summary(
                    validation_errors
                    + [
                        f"Only {len(validated_findings)} valid findings produced. "
                        f"Minimum is {MIN_COMPARISON_FINDINGS}."
                    ]
                )
                if attempt < max_attempts and len(validated_findings) < MIN_COMPARISON_FINDINGS:
                    decision_trace.append("correction_retry_allowed")
                else:
                    decision_trace.append("correction_retry_not_allowed")
            except Exception as exc:
                validation_error_summary = str(exc)
                decision_trace.append(f"validation_failed:{attempt}")
                if attempt == max_attempts:
                    return CompareResponse(success=False, error="LLM response could not be parsed", error_detail=str(exc))

        if len(validated_findings) < MIN_COMPARISON_FINDINGS:
            return CompareResponse(
                success=False,
                error="No valid diff report produced after retries",
                error_detail=validation_error_summary,
            )

        normalized_verdict = _compute_verdict(validated_findings)
        if verdict is not None:
            normalized_verdict.summary = verdict.summary
            normalized_verdict.recommendation = verdict.recommendation
        verdict = normalized_verdict
        decision_trace.extend(
            [
                f"verdict:{verdict.net_result.value}",
                f"a11y_regressions:{verdict.accessibility_regressions_count}",
            ]
        )

        report_id = f"DIFF-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{request_id}"
        report = DiffReport(
            report_id=report_id,
            level=2,
            baseline_filename=baseline.filename or "baseline",
            current_filename=current.filename or "current",
            baseline_resolution=baseline_meta.get("resolution"),
            current_resolution=current_meta.get("resolution"),
            llm_model_used=_llm_client.model,
            processing_time_seconds=round(time.time() - start_time, 2),
            findings=validated_findings,
            verdict=verdict,
            agent_notes=agent_notes,
            decision_trace=decision_trace,
            llm_attempts=llm_attempts,
        )

        try:
            report.decision_trace.append("report_persistence_started")
            save_diff_report_html(report, os.getenv("OUTPUT_DIR", "output"))
            report.decision_trace.append("reports_saved")
            save_diff_report_json(report, os.getenv("OUTPUT_DIR", "output"))
        except Exception as exc:
            logger.warning("Diff report save failed", extra={"request_id": request_id, "error": str(exc)})

        return CompareResponse(success=True, report=report)
    except Exception as exc:
        logger.exception("Unhandled compare failure")
        return CompareResponse(success=False, error="Compare request failed", error_detail=str(exc))
