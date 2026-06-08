"""Runtime guardrails for bounded, observable agent execution."""

from __future__ import annotations

import os


DEFAULT_MAX_LLM_ATTEMPTS = 1
MAX_ALLOWED_LLM_ATTEMPTS = 2
DEFAULT_MAX_L2_LLM_ATTEMPTS = 2
MAX_ALLOWED_L2_LLM_ATTEMPTS = 3


def parse_positive_int(value: str | None, default: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed < 1:
        return default
    return min(parsed, maximum)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_max_llm_attempts() -> int:
    """One LLM call by default; at most two if correction retry is enabled."""
    if not env_flag("ALLOW_LLM_CORRECTION_RETRY", default=False):
        return 1
    return parse_positive_int(
        os.getenv("LLM_MAX_ATTEMPTS"),
        default=DEFAULT_MAX_LLM_ATTEMPTS,
        maximum=MAX_ALLOWED_LLM_ATTEMPTS,
    )


def get_max_l2_llm_attempts() -> int:
    """Level 2 is harder: allow bounded correction by default, never unbounded loops."""
    return parse_positive_int(
        os.getenv("L2_LLM_MAX_ATTEMPTS"),
        default=DEFAULT_MAX_L2_LLM_ATTEMPTS,
        maximum=MAX_ALLOWED_L2_LLM_ATTEMPTS,
    )


def should_retry_llm(attempt: int, max_attempts: int, valid_findings_count: int) -> bool:
    return attempt < max_attempts and valid_findings_count < 3
