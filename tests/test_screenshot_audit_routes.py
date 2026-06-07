import io
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from api.screenshot_audit_routes import router, set_llm_client


class FakeLLMClient:
    provider = "groq"
    model = "fake-vision-model"

    def __init__(self):
        self.calls = 0

    def analyze_image(self, **kwargs):
        self.calls += 1
        return json.dumps(
            {
                "agent_notes": "API route smoke test.",
                "findings": [
                    {
                        "finding_id": "F001",
                        "principle": "visual_hierarchy",
                        "severity": "high",
                        "location": "Top header primary button",
                        "observation": "The primary action has the same visual weight as nearby navigation controls.",
                        "user_impact": "Users may miss the intended primary action.",
                        "recommendation": "Increase the primary action fill contrast and font weight.",
                        "confidence": 92.0,
                        "flagged_for_review": False,
                    },
                    {
                        "finding_id": "F002",
                        "principle": "spacing",
                        "severity": "medium",
                        "location": "Center card content section",
                        "observation": "Visible content groups appear tightly spaced inside the card.",
                        "user_impact": "Users may need more effort to scan related elements.",
                        "recommendation": "Increase vertical spacing between content groups using a consistent spacing token.",
                        "confidence": 84.0,
                        "flagged_for_review": False,
                    },
                    {
                        "finding_id": "F003",
                        "principle": "alignment",
                        "severity": "low",
                        "location": "Bottom form input row",
                        "observation": "Controls in the lower form row do not share a clear alignment line.",
                        "user_impact": "The interface feels less orderly and is slower to visually parse.",
                        "recommendation": "Align labels and input edges to a shared grid line across the row.",
                        "confidence": 79.0,
                        "flagged_for_review": False,
                    },
                ],
            }
        )


def make_image_bytes() -> bytes:
    image = Image.new("RGB", (800, 600), color=(245, 245, 245))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_analyze_route_is_complete_and_calls_llm_once_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOW_LLM_CORRECTION_RETRY", raising=False)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    fake_client = FakeLLMClient()
    set_llm_client(fake_client)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/v1/analyze",
        files={"file": ("screen.png", make_image_bytes(), "image/png")},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["report"]["summary"]["total"] == 3
    assert body["report"]["llm_attempts"] == 1
    assert "llm_attempt_limit:1" in body["report"]["decision_trace"]
    assert fake_client.calls == 1
