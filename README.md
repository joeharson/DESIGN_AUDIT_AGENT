# Design Audit Agent

AI-assisted visual quality platform for screenshot audits, before/after design comparison, and autonomous browser-based regression scans.

The project exposes a FastAPI service, a Streamlit operator UI, generated HTML/JSON reports, and SQLite-backed visual baselines for Level 3 scans.

## Capabilities

- Level 1 Audit: analyzes one screenshot and returns validated design findings.
- Level 2 Compare: compares baseline and current screenshots, classifying improvements, regressions, and neutral changes.
- Level 3 Scan: drives a browser with Playwright, captures configured pages, compares against saved baselines, and runs LLM review only when visual change is meaningful.
- Reports: persists JSON and HTML reports under `output/`.
- Baselines: stores Level 3 screenshot baselines and scan history in SQLite.

## Architecture

```text
api/          FastAPI route modules
core/         agent logic, schemas, prompts, validation, reporting, scan orchestration
frontend/     Streamlit workbench
backend/      deployable FastAPI package entrypoint
database/     Level 3 baseline storage package boundary
templates/    generated HTML report and upload templates
config/       scan configuration examples and generated UI config
tests/        pytest coverage
output/       generated reports, screenshots, baselines, and UI sessions
```

Important entrypoints:

- `main.py`: FastAPI application setup and router mounting.
- `backend/app.py`: package export for `uvicorn backend.app:app`.
- `frontend/audit_workbench.py`: Streamlit UI.
- `streamlit_app.py`: backward-compatible Streamlit launcher.
- `api/screenshot_audit_routes.py`: Level 1 endpoints.
- `api/screenshot_comparison_routes.py`: Level 2 endpoints.
- `api/regression_scan_routes.py`: Level 3 endpoints.
- `core/vision_model_client.py`: Groq vision client wrapper.
- `core/audit_report_writer.py`: JSON and HTML report persistence.
- `core/regression_scan_engine.py`: Level 3 scan orchestration.
- `core/visual_baseline_store.py`: SQLite baseline and scan history store.

## Requirements

- Docker Desktop or Docker Engine, recommended.
- Groq API key.
- Python 3.11 if running without Docker.

Runtime configuration is read from `.env`.

```env
GROQ_API_KEY=your_real_key_here
SCAN_USERNAME=your_test_account_username
SCAN_PASSWORD=your_test_account_password
```

`SCAN_USERNAME` and `SCAN_PASSWORD` are only needed for authenticated Level 3 scans.

## Run With Docker

```bash
copy .env.example .env
docker compose up --build
```

Open:

- Streamlit UI: `http://localhost:8501`
- API docs: `http://localhost:8001/docs`
- Upload UI: `http://localhost:8001/ui`
- Health check: `http://localhost:8001/api/v1/health`

Stop services:

```bash
docker compose down
```

Rebuild from a clean image:

```bash
docker compose down
docker compose build --no-cache
docker compose up
```

Docker installs Python dependencies, Playwright dependencies, Chromium, FastAPI, and Streamlit.

## Run Locally

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Start the API:

```bash
uvicorn backend.app:app --reload --port 8001
```

Start the UI in another terminal:

```bash
streamlit run frontend/audit_workbench.py
```

On Windows, restart FastAPI after installing Playwright. `main.py` sets the Windows event loop policy required by Playwright subprocesses.

## Streamlit Workflows

The Streamlit workbench has five sidebar workflows:

- `Level 1 Audit`
- `Level 2 Compare`
- `Level 3 Website Scan`
- `Baselines`
- `History`

UI sessions are stored under `output/ui_sessions/`, and the active session id is also kept in the browser URL. Use `Start new session` to clear the workspace.

## API Usage

### Health

```bash
curl http://localhost:8001/api/v1/health
```

### Level 1 Screenshot Audit

```bash
curl -X POST http://localhost:8001/api/v1/analyze ^
  -F "file=@C:\path\to\screenshot.png"
```

### Level 2 Screenshot Comparison

```bash
curl -X POST http://localhost:8001/api/v1/compare ^
  -F "baseline=@C:\path\to\before.png" ^
  -F "current=@C:\path\to\after.png"
```

Baseline means approved before/original. Current means after/candidate.

### Level 3 Regression Scan

Level 3 uses a JSON scan configuration with a target URL, at least three pages, optional authentication selectors, viewport dimensions, wait time, and dynamic selectors.

```bash
curl -X POST http://localhost:8001/api/v1/scan/start ^
  -H "Content-Type: application/json" ^
  -d "{\"config_file\":\"config/scan_config.example.json\",\"refresh_baseline\":false}"
```

Refresh reviewed baselines:

```bash
curl -X POST http://localhost:8001/api/v1/scan/baseline/refresh ^
  -H "Content-Type: application/json" ^
  -d "{\"config_file\":\"config/scan_config.example.json\",\"page_id\":\"all\"}"
```

Other Level 3 endpoints:

- `GET /api/v1/scan/baselines`
- `GET /api/v1/scan/history`

## Level 3 Behavior

First run:

- Opens the configured website with Playwright.
- Authenticates when auth is configured.
- Captures screenshots for configured pages.
- Saves baselines and baseline versions.
- Returns `overall_status: baseline_created`.

Later runs:

- Captures fresh screenshots.
- Compares against saved baselines.
- Skips LLM review when pixel diff is below `0.5%`.
- Uses the Level 2 comparison agent for meaningful visual changes.
- Stores scan reports and scan history.

If a page has `comparison_report: null`, the scan either created/refreshed a baseline, skipped LLM review because the pixel diff was small, or encountered a capture error listed on that page result.

## Output

- Level 1 JSON: `output/audit_{report_id}.json`
- Level 1 HTML: `output/audit_{report_id}.html`
- Level 2 JSON: `output/diff_{report_id}.json`
- Level 2 HTML: `output/diff_{report_id}.html`
- Level 3 reports: `output/scans/SCAN-*.json` and `output/scans/SCAN-*.html`
- Baseline screenshots: `output/baselines/{page_id}.png`
- Baseline database: `output/baselines/baselines.db`
- Baseline versions: `output/baselines/versions/`

## Guardrails

- LLM retries are bounded by environment-driven limits.
- Unsupported, corrupt, oversized, or very small images are rejected before model calls.
- LLM output must be valid JSON and pass Pydantic validation.
- Level 1 requires at least three valid findings.
- Level 2 requires at least five valid visual differences.
- Level 3 applies DOM masking and image-level filtering for dynamic regions.
- Level 3 has a 180-second scan budget.
- Failures return structured responses instead of uncaught server errors.
- Reports include `decision_trace` and `llm_attempts` for auditability.

## Tests

```bash
pytest tests/ -v
```

## Renamed Module Map

The LEVEL3 source files were renamed to match the naming style established by previous levels while preserving behavior.

| Area | Current responsibility |
| --- | --- |
| `api/screenshot_audit_routes.py` | Level 1 screenshot audit routes |
| `api/screenshot_comparison_routes.py` | Level 2 screenshot comparison routes |
| `api/regression_scan_routes.py` | Level 3 regression scan routes |
| `core/audit_contracts.py` | Level 1/shared Pydantic contracts |
| `core/comparison_audit_contracts.py` | Level 2 comparison contracts |
| `core/regression_scan_contracts.py` | Level 3 scan contracts |
| `core/audit_prompt_factory.py` | Level 1 prompt construction |
| `core/comparison_prompt_factory.py` | Level 2 prompt construction |
| `core/regression_scan_prompt_factory.py` | Level 3 prompt context |
| `core/retry_guardrails.py` | bounded retry configuration |
| `core/vision_model_client.py` | vision model client |
| `core/finding_validator.py` | LLM parsing and finding validation |
| `core/audit_report_writer.py` | JSON and HTML report writing |
| `core/browser_scan_runner.py` | Playwright browser automation |
| `core/dynamic_region_filter.py` | dynamic region masking and pixel diff |
| `core/regression_scan_engine.py` | Level 3 scan orchestration |
| `core/visual_baseline_store.py` | SQLite baseline persistence |
| `utils/screenshot_image_processing.py` | image validation, resizing, and encoding |
| `utils/structured_event_logging.py` | structured JSON logging |
| `frontend/audit_workbench.py` | Streamlit operator UI |

