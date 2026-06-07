"""FastAPI routes for Level 1 screenshot audit."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, UploadFile

from core.audit_contracts import AnalyzeResponse, AuditReport, HealthResponse
from core.audit_prompt_factory import SYSTEM_PROMPT_L1, build_correction_prompt, build_single_image_prompt
from core.audit_report_writer import save_html_report, save_json_report
from core.finding_validator import (
    build_validation_error_summary,
    compute_summary,
    parse_llm_response,
    validate_findings,
)
from core.retry_guardrails import get_max_llm_attempts, should_retry_llm
from utils.screenshot_image_processing import encode_image_to_base64, load_and_validate_image, resize_if_needed
from utils.structured_event_logging import get_logger

logger = get_logger(__name__)
router = APIRouter()
_llm_client = None


def set_llm_client(client) -> None:
    global _llm_client
    _llm_client = client


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="1.0.0",
        llm_provider=_llm_client.provider if _llm_client else "not initialized",
        llm_model=_llm_client.model if _llm_client else "not initialized",
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_screenshot(file: UploadFile = File(...)) -> AnalyzeResponse:
    try:
        request_id = str(uuid.uuid4())[:8].upper()
        start_time = time.time()
        validation_error_summary = ""
        decision_trace = ["request_received"]
        llm_attempts = 0
        logger.info("Analyze request received", extra={"request_id": request_id, "image_filename": file.filename})

        if _llm_client is None:
            return AnalyzeResponse(
                success=False,
                error="LLM client not initialized",
                error_detail="Restart the server after setting GROQ_API_KEY in .env.",
            )

        try:
            file_bytes = await file.read()
            image, metadata = load_and_validate_image(
                file_bytes,
                file.filename or "upload",
                max_size_mb=float(os.getenv("MAX_IMAGE_SIZE_MB", "10")),
            )
            decision_trace.append(f"image_validated:{metadata.get('resolution')}:{metadata.get('format')}")
        except ValueError as exc:
            return AnalyzeResponse(success=False, error="Image validation failed", error_detail=str(exc))

        try:
            image = resize_if_needed(image)
            image_base64 = encode_image_to_base64(image, fmt=metadata["format"])
            user_prompt = build_single_image_prompt(image_context=metadata)
            decision_trace.append("image_encoded")
        except Exception as exc:
            logger.exception("Image preparation failed", extra={"request_id": request_id})
            return AnalyzeResponse(success=False, error="Image preparation failed", error_detail=str(exc))

        validated_findings = []
        agent_notes = None
        max_attempts = get_max_llm_attempts()
        decision_trace.append(f"llm_attempt_limit:{max_attempts}")
        for attempt in range(1, max_attempts + 1):
            try:
                prompt = user_prompt if attempt == 1 else build_correction_prompt(validation_error_summary)
                llm_attempts += 1
                decision_trace.append(f"llm_call_started:{attempt}")
                raw_response = _llm_client.analyze_image(
                    system_prompt=SYSTEM_PROMPT_L1,
                    user_prompt=prompt,
                    image_base64=image_base64,
                    image_format=metadata["format"],
                )
                decision_trace.append(f"llm_call_completed:{attempt}")
            except Exception as exc:
                logger.exception("LLM call failed", extra={"request_id": request_id, "attempt": attempt})
                return AnalyzeResponse(success=False, error="LLM service unavailable", error_detail=str(exc))

            try:
                parsed = parse_llm_response(raw_response)
                agent_notes = parsed.get("agent_notes")
                validated_findings, validation_errors = validate_findings(parsed)
                decision_trace.append(f"validation_completed:{len(validated_findings)}_valid_findings")
                if len(validated_findings) >= 3:
                    break
                validation_error_summary = build_validation_error_summary(
                    validation_errors + [f"Only {len(validated_findings)} valid findings produced. Minimum is 3."]
                )
                if should_retry_llm(attempt, max_attempts, len(validated_findings)):
                    decision_trace.append("correction_retry_allowed")
                else:
                    decision_trace.append("correction_retry_not_allowed")
            except Exception as exc:
                validation_error_summary = str(exc)
                decision_trace.append(f"validation_failed:{attempt}")
                if attempt == max_attempts:
                    return AnalyzeResponse(success=False, error="LLM response could not be parsed", error_detail=str(exc))

        if len(validated_findings) < 3:
            return AnalyzeResponse(
                success=False,
                error="No valid findings produced after retries",
                error_detail=validation_error_summary,
            )

        report_id = f"RPT-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{request_id}"
        try:
            report = AuditReport(
                report_id=report_id,
                level=1,
                image_filename=file.filename or "upload",
                image_resolution=metadata.get("resolution"),
                llm_model_used=_llm_client.model,
                processing_time_seconds=round(time.time() - start_time, 2),
                findings=validated_findings,
                summary=compute_summary(validated_findings),
                agent_notes=agent_notes,
                decision_trace=decision_trace,
                llm_attempts=llm_attempts,
            )
        except Exception as exc:
            logger.exception("Report construction failed", extra={"request_id": request_id})
            return AnalyzeResponse(success=False, error="Report construction failed", error_detail=str(exc))

        output_dir = os.getenv("OUTPUT_DIR", "output")
        try:
            report.decision_trace.append("report_persistence_started")
            save_html_report(report, output_dir)
            report.decision_trace.append("reports_saved")
            save_json_report(report, output_dir)
        except Exception as exc:
            logger.warning("Report file save failed", extra={"request_id": request_id, "error": str(exc)})

        logger.info("Analysis complete", extra={"request_id": request_id, "report_id": report_id})
        return AnalyzeResponse(success=True, report=report)
    except Exception as exc:
        logger.exception("Unhandled analyze failure")
        return AnalyzeResponse(success=False, error="Analyze request failed", error_detail=str(exc))
