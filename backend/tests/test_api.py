import json
import re
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app import main
from app.llm.client import LLMClient
from app.llm.config import LLMSettings
from app.main import app
from app.pipeline import check_syntax
from app.schemas import MAX_CODE_CHARS

client = TestClient(app)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_valid_code_returns_clean_result():
    response = client.post("/analyze", json={"code": "def add(a, b):\n    return a + b\n"})
    assert response.status_code == 200
    body = response.json()
    assert body["issues"] == []
    assert body["score"] == 100
    assert body["tool_errors"] == {}
    assert set(body["summary"]) == {"critical", "high", "medium", "low", "info"}
    assert body["ai_review"]["enabled"] is False
    assert body["ai_review"]["error"] is None


def test_analyze_syntax_error_reports_line():
    code = "def ok():\n    return 1\n\ndef broken(:\n    pass\n"
    response = client.post("/analyze", json={"code": code})
    assert response.status_code == 200
    body = response.json()
    assert len(body["issues"]) == 1
    issue = body["issues"][0]
    assert issue["rule_id"] == "syntax-error"
    assert issue["category"] == "bug"
    assert issue["severity"] == "high"
    assert issue["line"] == 4
    assert body["summary"]["high"] == 1


def test_analyze_rejects_empty_code():
    response = client.post("/analyze", json={"code": ""})
    assert response.status_code == 422


def test_analyze_rejects_oversized_code():
    response = client.post("/analyze", json={"code": "x" * (MAX_CODE_CHARS + 1)})
    assert response.status_code == 422


def test_analyze_rejects_missing_code_field():
    response = client.post("/analyze", json={})
    assert response.status_code == 422


def test_buggy_sample_is_valid_python():
    # The fixture must parse, otherwise later analyzer tests would only see a syntax error.
    code = (SAMPLES_DIR / "buggy.py").read_text(encoding="utf-8")
    assert check_syntax(code) is None


# --- /analyze with the AI review (mocked LLM) ----------------------------------------------


def mock_llm(handler) -> LLMClient:
    settings = LLMSettings(provider="gemini", base_url="https://llm.test/v1", model="m", api_key="k")
    # sleep=no-op: retried 503s in these tests shouldn't really wait 2 s + 4 s.
    return LLMClient(settings, transport=httpx.MockTransport(handler), sleep=lambda seconds: None)


def dismiss_everything_model(request):
    """A worst-case model: calls every finding a false positive and adds the process() bug."""
    prompt = json.loads(request.content)["messages"][1]["content"]
    ids = re.findall(r"^(F\d+):", prompt, flags=re.MULTILINE)
    reply = {
        "findings": [{"id": fid, "verdict": "false_positive", "explanation": "looks fine"} for fid in ids],
        "new_issues": [{"line": 69, "category": "bug", "severity": "high", "rule": "unbound-local",
                        "title": "result is unbound if int() raises", "explanation": "..."}],
    }
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})


def test_analyze_with_ai_review(monkeypatch):
    monkeypatch.setattr(main, "llm_client", mock_llm(dismiss_everything_model))
    code = (SAMPLES_DIR / "buggy.py").read_text(encoding="utf-8")
    body = client.post("/analyze", json={"code": code}).json()
    issues, ai = body["issues"], body["ai_review"]

    assert (ai["enabled"], ai["error"], ai["provider"], ai["added"]) == (True, None, "gemini", 1)
    # The three critical security findings (os.system, shell=True, SQL) can't be dismissed.
    critical = [i for i in issues if i["severity"] == "critical"]
    assert len(critical) == 3 and all(i["ai"]["verdict"] == "confirmed" for i in critical)
    assert ai["overridden"] == 3
    assert any(i["tool"] == "ai" and i["line"] == 69 for i in issues)

    # False positives are listed last and don't count toward summary or score.
    dismissed = [i for i in issues if i["ai"] and i["ai"]["verdict"] == "false_positive"]
    assert dismissed and issues[-len(dismissed):] == dismissed
    assert sum(body["summary"].values()) == len(issues) - len(dismissed)


def test_llm_failure_falls_back_to_static_results(monkeypatch):
    monkeypatch.setattr(main, "llm_client", mock_llm(lambda request: httpx.Response(503, text="overloaded")))
    code = (SAMPLES_DIR / "buggy.py").read_text(encoding="utf-8")
    response = client.post("/analyze", json={"code": code})

    assert response.status_code == 200
    body = response.json()
    assert "503" in body["ai_review"]["error"]
    assert body["issues"] and all(issue["ai"] is None for issue in body["issues"])
