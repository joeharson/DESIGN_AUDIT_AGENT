# Agent Code

The agent implementation lives in `core/`:

- `vision_model_client.py` talks to Groq vision models.
- `audit_prompt_factory.py`, `comparison_prompt_factory.py`, and `regression_scan_prompt_factory.py` define agent instructions.
- `audit_contracts.py`, `comparison_audit_contracts.py`, and `regression_scan_contracts.py` define validation contracts.
- `finding_validator.py` parses and validates LLM JSON.
- `browser_scan_runner.py`, `regression_scan_engine.py`, `dynamic_region_filter.py`, and `visual_baseline_store.py` implement Level 3 autonomy.
- `audit_report_writer.py` writes JSON and HTML reports.

This folder documents the boundary: `core/` is the decision-making agent layer,
while `api/` is transport and `frontend/` is UI.
