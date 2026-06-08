"""Level 3 autonomous scan orchestration."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from pydantic import ValidationError

from core.browser_scan_runner import BrowserManager
from core.dynamic_region_filter import DynamicFilter
from core.retry_guardrails import get_max_l2_llm_attempts
from core.comparison_prompt_factory import SYSTEM_PROMPT_L2, build_l2_correction_prompt
from core.regression_scan_prompt_factory import build_regression_context_prompt
from core.audit_report_writer import (
    save_diff_report_html,
    save_diff_report_json,
    save_scan_report_html,
    save_scan_report_json,
)
from core.audit_contracts import ChangeDirection
from core.comparison_audit_contracts import (
    AccessibilityRegressionType,
    ComparisonFinding,
    DiffReport,
    OverallVerdict,
)
from core.regression_scan_contracts import PageConfig, PageScanResult, ScanConfig, ScanReport
from core.finding_validator import build_validation_error_summary, parse_llm_response
from utils.screenshot_image_processing import encode_image_to_base64
from utils.structured_event_logging import get_logger

logger = get_logger(__name__)


class ScanEngine:
    def __init__(self, llm_client, baseline_store, scan_config: ScanConfig, config_file: str) -> None:
        self.llm_client = llm_client
        self.baseline_store = baseline_store
        self.scan_config = scan_config
        self.config_file = config_file
        self.dynamic_filter = DynamicFilter()
        self.scan_id = f"SCAN-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
        self.started_at = datetime.now(UTC)

    async def run_scan(self, refresh_baseline: bool = False) -> ScanReport:
        start = time.time()
        decision_trace = [f"scan_started:{self.scan_id}", f"target:{self.scan_config.target_url}"]
        browser = BrowserManager(
            self.scan_config.viewport_width,
            self.scan_config.viewport_height,
            wait_after_navigation_ms=self.scan_config.wait_after_navigation_ms,
        )
        page_results: list[PageScanResult] = []
        scan_error: str | None = None

        try:
            await browser.start()
            if self.scan_config.auth:
                decision_trace.append("auth_started")
                authenticated = await browser.authenticate(self.scan_config.auth)
                decision_trace.append(f"auth_result:{authenticated}")
                if not authenticated:
                    return self._finalize_report(page_results, decision_trace, start, "error", "Authentication failed")

            for page_config in self.scan_config.pages:
                if time.time() - start > 180:
                    decision_trace.append("scan_time_budget_exceeded")
                    break
                page_results.append(await self.scan_page(page_config, browser, refresh_baseline))
        except Exception as exc:
            logger.exception("scan cycle failed", extra={"scan_id": self.scan_id})
            scan_error = str(exc) or exc.__class__.__name__
            decision_trace.append(f"scan_error:{scan_error}")
        finally:
            await browser.stop()

        if scan_error:
            return self._finalize_report(page_results, decision_trace, start, "error", scan_error)
        return self._finalize_report(page_results, decision_trace, start)

    async def scan_page(self, page_config: PageConfig, browser: BrowserManager, refresh_baseline: bool) -> PageScanResult:
        page_start = time.time()
        url = page_config.url if page_config.url.startswith("http") else (
        page_config.url if page_config.url.startswith("/") else "/" + page_config.url)
        page_url = urljoin(self.scan_config.target_url.rstrip("/") + "/", url)
        baseline_key = self._baseline_key(page_config.page_id)
        resolved_page = page_config.model_copy(update={"url": page_url})
        trace = [f"page_navigation_started:{page_config.page_id}"]

        baseline = self.baseline_store.get_baseline(baseline_key)
        capture = await browser.navigate_and_capture(resolved_page, self.scan_config.scan_output_dir)
        if not capture.get("success"):
            trace.append(f"page_capture_failed:{page_config.page_id}")
            return PageScanResult(
                page_id=page_config.page_id,
                page_url=page_url,
                baseline_exists=baseline is not None,
                error=capture.get("error") or "Capture failed",
                dynamic_regions_filtered=int(capture.get("dynamic_regions_filtered") or 0),
                pixel_diff_percentage=None,
                scan_duration_seconds=round(time.time() - page_start, 2),
                decision_trace=trace,
            )

        screenshot_path = capture["screenshot_path"]
        if baseline is None or refresh_baseline:
            saved_path = self.baseline_store.save_baseline(baseline_key, page_url, screenshot_path, self.scan_id)
            trace.append(f"baseline_refreshed:{page_config.page_id}" if refresh_baseline and baseline else f"baseline_created:{page_config.page_id}")
            return PageScanResult(
                page_id=page_config.page_id,
                page_url=page_url,
                page_title=capture.get("page_title", ""),
                screenshot_path=screenshot_path,
                baseline_exists=False,
                baseline_screenshot_path=saved_path,
                dynamic_regions_filtered=int(capture.get("dynamic_regions_filtered") or 0),
                pixel_diff_percentage=None,
                scan_duration_seconds=round(time.time() - page_start, 2),
                decision_trace=trace + [f"page_scan_complete:{page_config.page_id}:baseline_created"],
            )

        baseline_path = baseline["screenshot_path"]
        filtered_baseline, filtered_current, image_filtered_count = self.dynamic_filter.filter_for_comparison(
            baseline_path,
            screenshot_path,
            page_config.dynamic_selectors,
        )
        pixel_diff = self.dynamic_filter.compute_pixel_diff_percentage(filtered_baseline, filtered_current)
        total_filtered = int(capture.get("dynamic_regions_filtered") or 0) + image_filtered_count
        trace.append(f"pixel_diff:{pixel_diff}")

        if pixel_diff < 0.5:
            trace.append(f"no_significant_diff:{page_config.page_id}")
            return PageScanResult(
                page_id=page_config.page_id,
                page_url=page_url,
                page_title=capture.get("page_title", ""),
                screenshot_path=screenshot_path,
                baseline_exists=True,
                baseline_screenshot_path=baseline_path,
                dynamic_regions_filtered=total_filtered,
                pixel_diff_percentage=pixel_diff,
                scan_duration_seconds=round(time.time() - page_start, 2),
                decision_trace=trace + [f"page_scan_complete:{page_config.page_id}:pass"],
            )

        comparison_report = self._run_l2_comparison(
            page_config=page_config,
            page_url=page_url,
            baseline_path=filtered_baseline,
            current_path=filtered_current,
            pixel_diff_percentage=pixel_diff,
            dynamic_regions_filtered=total_filtered,
            trace=trace,
        )
        status = comparison_report.verdict.net_result.value if comparison_report else "error"
        return PageScanResult(
            page_id=page_config.page_id,
            page_url=page_url,
            page_title=capture.get("page_title", ""),
            screenshot_path=screenshot_path,
            baseline_exists=True,
            baseline_screenshot_path=baseline_path,
            comparison_report=comparison_report,
            dynamic_regions_filtered=total_filtered,
            pixel_diff_percentage=pixel_diff,
            scan_duration_seconds=round(time.time() - page_start, 2),
            error=None if comparison_report else "Comparison failed after retries",
            decision_trace=trace + [f"page_scan_complete:{page_config.page_id}:{status}"],
        )

    def _run_l2_comparison(
        self,
        page_config: PageConfig,
        page_url: str,
        baseline_path: str,
        current_path: str,
        pixel_diff_percentage: float,
        dynamic_regions_filtered: int,
        trace: list[str],
    ) -> DiffReport | None:
        from PIL import Image

        baseline_image = Image.open(baseline_path)
        current_image = Image.open(current_path)
        baseline_b64 = encode_image_to_base64(baseline_image, fmt="PNG")
        current_b64 = encode_image_to_base64(current_image, fmt="PNG")
        prompt = build_regression_context_prompt(
            page_config.name,
            page_url,
            pixel_diff_percentage,
            dynamic_regions_filtered,
        )
        validation_error_summary = ""
        max_attempts = get_max_l2_llm_attempts()
        findings: list[ComparisonFinding] = []
        verdict: OverallVerdict | None = None
        agent_notes = None
        attempts = 0

        for attempt in range(1, max_attempts + 1):
            try:
                attempts += 1
                trace.append(f"l3_llm_call_started:{attempt}")
                raw = self.llm_client.analyze_two_images(
                    system_prompt=SYSTEM_PROMPT_L2,
                    user_prompt=prompt if attempt == 1 else build_l2_correction_prompt(validation_error_summary),
                    image_base64_1=baseline_b64,
                    image_format_1="PNG",
                    image_base64_2=current_b64,
                    image_format_2="PNG",
                )
                parsed = parse_llm_response(raw)
                agent_notes = parsed.get("agent_notes")
                findings, verdict, errors = self._validate_comparison_response(parsed)
                findings = self._attach_regression_evidence(findings, pixel_diff_percentage, dynamic_regions_filtered)
                trace.append(f"l3_validation_completed:{len(findings)}_valid_findings")
                minimum = 3 if pixel_diff_percentage < 2 else 5
                if len(findings) >= minimum:
                    break
                validation_error_summary = build_validation_error_summary(
                    errors + [f"Only {len(findings)} valid findings produced. Minimum is {minimum}."]
                )
            except Exception as exc:
                validation_error_summary = str(exc)
                trace.append(f"l3_comparison_attempt_failed:{attempt}")

        if not findings:
            logger.warning("Level 3 comparison produced no findings", extra={"page_id": page_config.page_id})
            return None

        normalized_verdict = self._compute_verdict(findings)
        if verdict is not None:
            normalized_verdict.summary = verdict.summary
            normalized_verdict.recommendation = verdict.recommendation

        report = DiffReport(
            report_id=f"{self.scan_id}-{page_config.page_id}",
            level=2,
            baseline_filename=Path(baseline_path).name,
            current_filename=Path(current_path).name,
            baseline_resolution=f"{baseline_image.width}x{baseline_image.height}",
            current_resolution=f"{current_image.width}x{current_image.height}",
            llm_model_used=self.llm_client.model,
            findings=findings,
            verdict=normalized_verdict,
            agent_notes=agent_notes,
            decision_trace=trace.copy(),
            llm_attempts=attempts,
        )
        save_diff_report_html(report, self.scan_config.scan_output_dir)
        save_diff_report_json(report, self.scan_config.scan_output_dir)
        return report

    def _finalize_report(
        self,
        page_results: list[PageScanResult],
        decision_trace: list[str],
        start_time: float,
        forced_status: str | None = None,
        forced_error: str | None = None,
    ) -> ScanReport:
        completed_at = datetime.now(UTC)
        status = forced_status or self.compute_overall_status(page_results)
        if forced_error:
            decision_trace.append(f"scan_forced_error:{forced_error}")
        report = ScanReport(
            scan_id=self.scan_id,
            config_file=self.config_file,
            target_url=self.scan_config.target_url,
            scan_started_at=self.started_at,
            scan_completed_at=completed_at,
            total_duration_seconds=round(time.time() - start_time, 2),
            pages_scanned=len(page_results),
            pages_with_regressions=sum(
                1
                for result in page_results
                if result.comparison_report and result.comparison_report.verdict.net_result == ChangeDirection.REGRESSION
            ),
            pages_with_errors=sum(1 for result in page_results if result.error),
            page_results=page_results,
            overall_status=status,
            llm_model_used=self.llm_client.model,
            decision_trace=decision_trace,
        )
        save_scan_report_html(report, self.scan_config.scan_output_dir)
        save_scan_report_json(report, self.scan_config.scan_output_dir)
        self.baseline_store.save_scan_run(
            self.scan_id,
            self.config_file,
            self.scan_config.target_url,
            self.started_at,
            report.overall_status,
            report.pages_scanned,
            report.pages_with_regressions,
            report.json_report_path,
        )
        return report

    @staticmethod
    def compute_overall_status(page_results: list[PageScanResult]) -> str:
        if not page_results:
            return "error"
        if page_results and all(not result.baseline_exists and not result.error for result in page_results):
            return "baseline_created"
        if any(
            result.comparison_report and result.comparison_report.verdict.net_result == ChangeDirection.REGRESSION
            for result in page_results
        ):
            return "regression"
        if any(result.error for result in page_results) and not any(result.comparison_report for result in page_results):
            return "error"
        return "pass"

    @staticmethod
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
            verdict = ScanEngine._compute_verdict(findings)
            errors.append(f"Verdict: {exc}")
        return findings, verdict, errors

    @staticmethod
    def _attach_regression_evidence(
        findings: list[ComparisonFinding],
        pixel_diff_percentage: float,
        dynamic_regions_filtered: int,
    ) -> list[ComparisonFinding]:
        enriched: list[ComparisonFinding] = []
        for finding in findings:
            measurements = dict(finding.pixel_measurements or {})
            measurements.setdefault("page_pixel_diff_percentage", f"{pixel_diff_percentage:.4f}%")
            measurements.setdefault("affected_region", finding.location)
            measurements.setdefault("dynamic_regions_filtered_before_analysis", str(dynamic_regions_filtered))
            finding.pixel_measurements = measurements
            enriched.append(finding)
        return enriched

    @staticmethod
    def _compute_verdict(findings: list[ComparisonFinding]) -> OverallVerdict:
        improvement_count = sum(1 for finding in findings if finding.change_direction == ChangeDirection.IMPROVEMENT)
        regression_count = sum(1 for finding in findings if finding.change_direction == ChangeDirection.REGRESSION)
        neutral_count = sum(1 for finding in findings if finding.change_direction == ChangeDirection.NEUTRAL)
        a11y_count = sum(1 for finding in findings if finding.accessibility_regression != AccessibilityRegressionType.NONE)
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
            summary=f"Autonomous scan found {regression_count} regressions, {improvement_count} improvements, and {neutral_count} neutral changes.",
            recommendation="Review regression findings before refreshing the baseline.",
        )

    def _baseline_key(self, page_id: str) -> str:
        target = self.scan_config.target_url.lower().replace("https://", "").replace("http://", "")
        target = target.strip("/").replace("www.", "")
        safe_target = "".join(ch if ch.isalnum() else "_" for ch in target).strip("_")
        safe_page = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in page_id).strip("_")
        return f"{safe_target}__{safe_page}"
