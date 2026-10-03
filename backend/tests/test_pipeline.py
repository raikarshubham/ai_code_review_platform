"""End-to-end pipeline tests that run the real analyzers (a few seconds)."""

import subprocess
from pathlib import Path

import pytest

from app.pipeline import analyze

BUGGY_CODE = (Path(__file__).resolve().parent.parent / "samples" / "buggy.py").read_text(
    encoding="utf-8"
)

CLEAN_CODE = "def add(a, b):\n    return a + b\n"


@pytest.fixture(scope="module")
def buggy_result():
    # Analyze once and share across tests: the real tools take a couple of seconds.
    return analyze(BUGGY_CODE)


def find(result, rule_id):
    return [issue for issue in result.issues if issue.rule_id == rule_id]


@pytest.mark.parametrize(
    ("rule_id", "severity"),
    [
        ("W0102", "high"),  # mutable default argument
        ("W0702", "high"),  # bare except
        ("B602", "critical"),  # subprocess shell=True
        ("B605", "critical"),  # os.system
        ("B608", "critical"),  # SQL injection
        ("B301", "high"),  # pickle.loads
        ("B105", "high"),  # hardcoded password
        ("B324", "medium"),  # md5
        ("B403", "info"),  # import pickle
        ("B404", "info"),  # import subprocess
    ],
)
def test_buggy_sample_findings(buggy_result, rule_id, severity):
    matches = find(buggy_result, rule_id)
    assert matches, f"{rule_id} not found"
    assert matches[0].severity == severity


def test_buggy_sample_no_tool_errors(buggy_result):
    assert buggy_result.tool_errors == {}


def test_clean_code_has_no_issues():
    result = analyze(CLEAN_CODE)
    assert result.issues == []
    assert result.score == 100
    assert result.tool_errors == {}


def test_tool_timeout_is_reported_not_fatal(monkeypatch):
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        # Simulate Pylint hanging; let the other tools run normally.
        if "pylint" in command:
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = analyze(BUGGY_CODE)

    assert "timed out" in result.tool_errors["pylint"]
    assert not any(issue.tool == "pylint" for issue in result.issues)
    assert any(issue.tool == "bandit" for issue in result.issues)
