"""Unit tests for each analyzer's output parser, using canned JSON (no subprocesses)."""

import json

import pytest

from app.analyzers import bandit_runner, pylint_runner
from app.analyzers.runner import AnalyzerError


def pylint_msg(message_id, msg_type, symbol="some-symbol", line=1, end_line=None):
    return {
        "type": msg_type,
        "module": "snippet",
        "obj": "",
        "line": line,
        "column": 0,
        "endLine": end_line,
        "endColumn": None,
        "path": "snippet.py",
        "symbol": symbol,
        "message": f"{symbol} message",
        "message-id": message_id,
    }


def bandit_result(test_id, severity="LOW", line=1, line_range=None):
    return {
        "test_id": test_id,
        "test_name": "some_test",
        "issue_severity": severity,
        "issue_confidence": "HIGH",
        "issue_text": f"{test_id} text",
        "line_number": line,
        "line_range": line_range or [line],
    }


def by_rule(issues):
    return {issue.rule_id: issue for issue in issues}


# --- Pylint -----------------------------------------------------------------------------


def test_pylint_type_mapping():
    output = json.dumps([
        pylint_msg("E1101", "error"),
        pylint_msg("W0101", "warning"),
        pylint_msg("R1705", "refactor"),
        pylint_msg("C0209", "convention"),
    ])
    issues = by_rule(pylint_runner.parse(output))
    assert (issues["E1101"].category, issues["E1101"].severity) == ("bug", "high")
    assert (issues["W0101"].category, issues["W0101"].severity) == ("bug", "medium")
    assert (issues["R1705"].category, issues["R1705"].severity) == ("smell", "low")
    assert (issues["C0209"].category, issues["C0209"].severity) == ("style", "info")


def test_pylint_calibrated_overrides():
    output = json.dumps([
        pylint_msg("W0102", "warning", "dangerous-default-value", line=16),
        pylint_msg("W0702", "warning", "bare-except", line=26, end_line=27),
        pylint_msg("W0612", "warning", "unused-variable"),
        pylint_msg("W0123", "warning", "eval-used"),
    ])
    issues = by_rule(pylint_runner.parse(output))
    assert (issues["W0102"].category, issues["W0102"].severity) == ("bug", "high")
    assert (issues["W0702"].severity, issues["W0702"].end_line) == ("high", 27)
    assert (issues["W0612"].category, issues["W0612"].severity) == ("smell", "low")
    assert (issues["W0123"].category, issues["W0123"].severity) == ("security", "high")
    assert issues["W0102"].tool == "pylint"
    assert issues["W0102"].symbol == "dangerous-default-value"


def test_pylint_empty_output_list():
    assert pylint_runner.parse("[]") == []


def test_pylint_invalid_json_raises():
    with pytest.raises(AnalyzerError):
        pylint_runner.parse("Traceback (most recent call last): ...")


# --- Bandit -----------------------------------------------------------------------------


def test_bandit_severity_overrides():
    output = json.dumps({"results": [
        bandit_result("B605", "HIGH"),   # os.system -> critical
        bandit_result("B608", "MEDIUM"),  # SQL injection -> critical
        bandit_result("B105", "LOW"),    # hardcoded password -> high
        bandit_result("B324", "HIGH"),   # md5 -> medium (Bandit overstates this one)
        bandit_result("B404", "LOW"),    # import subprocess -> info
    ]})
    issues = by_rule(bandit_runner.parse(output))
    assert issues["B605"].severity == "critical"
    assert issues["B608"].severity == "critical"
    assert issues["B105"].severity == "high"
    assert issues["B324"].severity == "medium"
    assert issues["B404"].severity == "info"
    assert all(issue.category == "security" for issue in issues.values())


def test_bandit_default_severity_for_unlisted_rule():
    output = json.dumps({"results": [bandit_result("B110", "LOW")]})
    assert bandit_runner.parse(output)[0].severity == "low"


def test_bandit_end_line_from_line_range():
    output = json.dumps({"results": [bandit_result("B608", line=10, line_range=[10, 11, 12])]})
    issue = bandit_runner.parse(output)[0]
    assert (issue.line, issue.end_line) == (10, 12)


@pytest.mark.parametrize("bad_output", ["not json", "{}", "[]"])
def test_bandit_unexpected_output_raises(bad_output):
    with pytest.raises(AnalyzerError):
        bandit_runner.parse(bad_output)
