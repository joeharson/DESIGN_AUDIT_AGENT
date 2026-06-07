from core.retry_guardrails import get_max_llm_attempts, parse_positive_int, should_retry_llm


def test_parse_positive_int_bounds_values():
    assert parse_positive_int("3", default=1, maximum=2) == 2
    assert parse_positive_int("0", default=1, maximum=2) == 1
    assert parse_positive_int("not-a-number", default=1, maximum=2) == 1


def test_default_max_llm_attempts_is_one(monkeypatch):
    monkeypatch.delenv("ALLOW_LLM_CORRECTION_RETRY", raising=False)
    monkeypatch.delenv("LLM_MAX_ATTEMPTS", raising=False)
    assert get_max_llm_attempts() == 1


def test_retry_must_be_explicit_and_capped(monkeypatch):
    monkeypatch.setenv("ALLOW_LLM_CORRECTION_RETRY", "true")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "9")
    assert get_max_llm_attempts() == 2


def test_should_retry_only_when_below_minimum_and_attempts_remain():
    assert should_retry_llm(attempt=1, max_attempts=2, valid_findings_count=2) is True
    assert should_retry_llm(attempt=2, max_attempts=2, valid_findings_count=2) is False
    assert should_retry_llm(attempt=1, max_attempts=2, valid_findings_count=3) is False
