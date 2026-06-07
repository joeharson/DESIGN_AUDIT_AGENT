"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from api.screenshot_audit_routes import router, set_llm_client
from core.vision_model_client import LLMClient
from utils.structured_event_logging import get_logger

load_dotenv()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Design Audit Agent starting up...")
    client = LLMClient()
    set_llm_client(client)
    logger.info("Startup complete", extra={"provider": client.provider, "model": client.model})
    yield
    logger.info("Design Audit Agent shutting down.")


app = FastAPI(
    title="Design Audit Agent",
    description="Level 1 AI agent for single-screenshot design audits.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1", tags=["Design Audit - Level 1"])


@app.get("/")
async def root() -> dict:
    return {
        "agent": "Design Audit Agent",
        "level": 1,
        "docs": "/docs",
        "health": "/api/v1/health",
        "analyze": "POST /api/v1/analyze",
    }
