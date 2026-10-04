from pathlib import Path

from fastapi.testclient import TestClient

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
