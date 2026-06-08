"""FastAPI routes for Level 3 autonomous regression scans."""

from __future__ import annotations

import json
import os
import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from core.visual_baseline_store import BaselineStore, baseline_store
from core.regression_scan_engine import ScanEngine
from core.regression_scan_contracts import BaselineInfo, ScanConfig, ScanResponse
from utils.structured_event_logging import get_logger

logger = get_logger(__name__)
router_l3 = APIRouter()
_llm_client = None


class ScanStartRequest(BaseModel):
    config_file: str
    refresh_baseline: bool = False


class BaselineRefreshRequest(BaseModel):
    config_file: str
    page_id: str = "all"


def set_llm_client_l3(client) -> None:
    global _llm_client
    _llm_client = client


@router_l3.post("/scan/start", response_model=ScanResponse)
async def start_scan(request: ScanStartRequest) -> ScanResponse:
    request_id = str(uuid.uuid4())[:8].upper()
    logger.info("Level 3 scan requested", extra={"request_id": request_id, "config_file": request.config_file})
    if _llm_client is None:
        return ScanResponse(success=False, error="LLM client not initialized", error_detail="Set GROQ_API_KEY and restart.")
    try:
        scan_config = _load_scan_config(request.config_file)
        store = _store_for_config(scan_config)
        engine = ScanEngine(_llm_client, store, scan_config, request.config_file)
        report = await asyncio.to_thread(_run_scan_in_playwright_loop, engine, request.refresh_baseline)
        report.decision_trace.insert(0, f"request_id:{request_id}")
        return ScanResponse(success=report.overall_status != "error", report=report)
    except Exception as exc:
        logger.exception("Level 3 scan failed", extra={"request_id": request_id})
        return ScanResponse(success=False, error="Scan failed", error_detail=str(exc))


@router_l3.get("/scan/baselines", response_model=list[BaselineInfo])
async def list_scan_baselines() -> list[BaselineInfo]:
    return [
        BaselineInfo(
            page_id=row["page_id"],
            page_url=row["page_url"],
            baseline_path=row["screenshot_path"],
            created_at=row["created_at"],
            size_bytes=row.get("size_bytes", 0),
        )
        for row in baseline_store.list_baselines()
    ]


@router_l3.post("/scan/baseline/refresh", response_model=ScanResponse)
async def refresh_scan_baseline(request: BaselineRefreshRequest) -> ScanResponse:
    request_id = str(uuid.uuid4())[:8].upper()
    if _llm_client is None:
        return ScanResponse(success=False, error="LLM client not initialized", error_detail="Set GROQ_API_KEY and restart.")
    try:
        scan_config = _load_scan_config(request.config_file)
        if request.page_id != "all":
            scan_config.pages = [page for page in scan_config.pages if page.page_id == request.page_id]
            if not scan_config.pages:
                return ScanResponse(success=False, error="Page not found", error_detail=f"No page_id '{request.page_id}' in config.")
        store = _store_for_config(scan_config)
        engine = ScanEngine(_llm_client, store, scan_config, request.config_file)
        report = await asyncio.to_thread(_run_scan_in_playwright_loop, engine, True)
        report.decision_trace.insert(0, f"request_id:{request_id}")
        return ScanResponse(success=report.overall_status != "error", report=report)
    except Exception as exc:
        logger.exception("Level 3 baseline refresh failed", extra={"request_id": request_id})
        return ScanResponse(success=False, error="Baseline refresh failed", error_detail=str(exc))


@router_l3.get("/scan/history")
async def scan_history() -> list[dict]:
    return baseline_store.get_scan_history(limit=10)


def _load_scan_config(config_file: str) -> ScanConfig:
    path = Path(config_file)
    if not path.exists():
        raise FileNotFoundError(f"Scan config file does not exist: {config_file}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ScanConfig.model_validate(data)


def _store_for_config(scan_config: ScanConfig) -> BaselineStore:
    db_path = os.getenv("BASELINE_DB_PATH") or str(Path(scan_config.baseline_dir) / "baselines.db")
    store = BaselineStore(db_path)
    store.initialize()
    return store


def _run_scan_in_playwright_loop(engine: ScanEngine, refresh_baseline: bool):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(engine.run_scan(refresh_baseline=refresh_baseline))
    finally:
        loop.close()
