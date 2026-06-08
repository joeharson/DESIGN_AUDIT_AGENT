"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from api.screenshot_audit_routes import router, set_llm_client
from api.screenshot_comparison_routes import router_l2, set_llm_client_l2
from api.regression_scan_routes import router_l3, set_llm_client_l3
from core.visual_baseline_store import baseline_store
from core.vision_model_client import LLMClient
from utils.structured_event_logging import get_logger

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Design Audit Agent starting up...")
    baseline_store.initialize()
    client = LLMClient()
    set_llm_client(client)
    set_llm_client_l2(client)
    set_llm_client_l3(client)
    logger.info("Startup complete", extra={"provider": client.provider, "model": client.model})
    yield
    logger.info("Design Audit Agent shutting down.")


app = FastAPI(
    title="Design Audit Agent",
    description="Level 1 audits, Level 2 design diffs, and Level 3 autonomous regression scans.",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1", tags=["Design Audit - Level 1"])
app.include_router(router_l2, prefix="/api/v1", tags=["Design Audit - Level 2"])
app.include_router(router_l3, prefix="/api/v1", tags=["Design Audit - Level 3"])


@app.get("/")
async def root() -> dict:
    return {
        "agent": "Design Audit Agent",
        "level": 3,
        "docs": "/docs",
        "ui": "/ui",
        "health": "/api/v1/health",
        "analyze": "POST /api/v1/analyze",
        "compare": "POST /api/v1/compare",
        "scan_start": "POST /api/v1/scan/start",
        "scan_baselines": "GET /api/v1/scan/baselines",
        "scan_refresh": "POST /api/v1/scan/baseline/refresh",
        "scan_history": "GET /api/v1/scan/history",
    }


@app.get("/ui", response_class=HTMLResponse)
async def upload_ui() -> HTMLResponse:
    from pathlib import Path

    html = (Path(__file__).parent / "templates" / "screenshot_upload_console.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
