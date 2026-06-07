# Design Audit Agent - Level 1

AI agent that analyzes UI screenshots with Groq vision models for design issues across five principles:
Visual Hierarchy, WCAG AA Contrast, Spacing, Alignment, and Consistency.

## Setup

```bash
cd design-audit-agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configure Environment

Copy `.env.example` to `.env` and replace the placeholder key.

```bash
copy .env.example .env
```

Set your Groq API key:

- `GROQ_API_KEY=your_real_key_here`

## Run

```bash
uvicorn main:app --reload --port 8001
```

Open `http://localhost:8001/docs`.

## Run With Docker

```bash
docker compose up --build
```

The API will be available at `http://localhost:8001/docs`. Reports are written to the local `output/` folder through the compose volume.

## Analyze A Screenshot

```bash
curl -X POST http://localhost:8001/api/v1/analyze \-F "file=@C:\path\to\screenshot.png"
```

## Output

- JSON report: `output/audit_{report_id}.json`
- HTML report: `output/audit_{report_id}.html`
- Structured JSON response from `POST /api/v1/analyze`
- `decision_trace` records observable execution decisions such as image validation, LLM attempt limit, validation result, and report writing.
- `llm_attempts` records the exact number of LLM calls made.

## Guardrails

- One LLM call by default: `ALLOW_LLM_CORRECTION_RETRY=false`.
- Optional correction retry is capped at two total attempts with `ALLOW_LLM_CORRECTION_RETRY=true` and `LLM_MAX_ATTEMPTS=2`.
- Image uploads reject unsupported formats, corrupt files, files over `MAX_IMAGE_SIZE_MB`, and images smaller than 100px.
- LLM output must be valid JSON and match the Pydantic finding schema before a report is produced.
- Failures return structured `success: false` responses instead of unhandled server errors.

## Run Tests

```bash
pytest tests/ -v
```

## Production Readiness Checklist

- Python dependencies are pinned in `requirements.txt`.
- Runtime configuration comes from `.env`; secrets are excluded from Docker and git.
- Docker support is included for repeatable deployment.
- The service exposes `/api/v1/health` for operational checks.
- Reports are persisted as JSON and HTML.
- Guardrails prevent unbounded LLM loops and record `decision_trace` plus `llm_attempts`.

## Architecture

- `main.py`: FastAPI app startup
- `api/screenshot_audit_routes.py`: HTTP endpoints
- `core/audit_contracts.py`: Pydantic contracts shared by future levels
- `core/audit_prompt_factory.py`: Level 1 prompt construction
- `core/vision_model_client.py`: Groq vision wrapper
- `core/finding_validator.py`: LLM JSON parsing and validation
- `core/audit_report_writer.py`: JSON and HTML report generation
- `utils/screenshot_image_processing.py`: Image loading, validation, resizing, encoding
- `utils/structured_event_logging.py`: Structured JSON logging

## Level 2 And 3 Extension Points

- Add `api/routes_l2.py` with `POST /compare`
- Add `core/audit_prompt_factory.build_comparison_prompt()`
- Add `core/audit_contracts.ComparisonFinding(Finding)` and `DiffReport`
- Level 3 adds browser automation and baseline storage
