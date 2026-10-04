"""Reviewer prompt and validation. The LLM is always a mock."""

import json
from pathlib import Path

import httpx
import pytest

from app.languages import SPECS, Language
from app.llm.client import LLMClient, LLMError
from app.llm.config import LLMSettings
from app.llm.prompt import build_messages, number_lines
from app.llm.reviewer import MAX_NEW_ISSUES, merge, review
from app.schemas import Issue, Verdict

PROCESS_BUG_CODE = (Path(__file__).resolve().parent.parent / "samples" / "buggy.py").read_text(encoding="utf-8")
PYTHON = SPECS[Language.PYTHON]
TEN_LINES = 10


def issue(line=1, rule_id="R1", category="bug", severity="high", tool="pylint", message="m"):
    return Issue(tool=tool, rule_id=rule_id, category=category, severity=severity, line=line, message=message)


def note(fid, verdict="confirmed", **extra):
    return {"id": fid, "verdict": verdict, "explanation": "because", **extra}


def new(line=3, **extra):
    item = {"line": line, "category": "bug", "severity": "high", "rule": "Unbound Var",
            "title": "x may be unbound", "explanation": "why"}
    return {**item, **extra}


def run_merge(reply, issues, line_count=TEN_LINES):
    findings = {f"F{n}": i for n, i in enumerate(issues, start=1)}
    return merge(reply, issues, findings, line_count)


# --- Prompt ---------------------------------------------------------------------------------


def test_number_lines_pads_to_the_widest_number():
    numbered = number_lines("\n".join(f"l{n}" for n in range(1, 11)))
    assert numbered.splitlines()[0] == " 1 | l1"
    assert numbered.splitlines()[9] == "10 | l10"


def test_prompt_has_language_fence_numbered_code_and_finding_ids():
    messages = build_messages("x = 1\n", SPECS[Language.GO], {"F1": issue(line=1, message="boom")})
    user = messages[1]["content"]
    assert "Language: Go" in user
    assert "```go\n1 | x = 1\n```" in user
    assert "F1: line 1, pylint R1, bug/high: boom" in user


def test_prompt_uses_a_longer_fence_when_code_contains_one():
    user = build_messages('doc = """```"""\n', PYTHON, {})[1]["content"]
    assert "````python" in user
    assert "(none)" in user


# --- Validation rules -----------------------------------------------------------------------


def test_verdicts_are_applied_and_counted():
    issues = [issue(line=1), issue(line=2)]
    merged, status = run_merge({"findings": [note("F1"), note("F2", "false_positive")]}, issues)
    assert merged[0].ai.verdict == Verdict.CONFIRMED
    assert merged[1].is_false_positive
    assert (status.enabled, status.confirmed, status.false_positives) == (True, 1, 1)


def test_rule1_unknown_ids_are_dropped_and_unmentioned_findings_untouched():
    merged, status = run_merge({"findings": [note("F9"), note("F1", "maybe")]}, [issue()])
    assert merged[0].ai is None
    assert status.confirmed == status.false_positives == 0


@pytest.mark.parametrize("line, end_line", [(0, None), (11, None), (5, 4), (5, 99), (True, None), ("3", None)])
def test_rule2_new_issues_with_bad_lines_are_dropped(line, end_line):
    merged, status = run_merge({"new_issues": [new(line=line, end_line=end_line)]}, [])
    assert merged == [] and status.added == 0


def test_rule2_fixed_code_needs_a_valid_range():
    reply = {"findings": [
        note("F1", fix="use None", fixed_code="ok()", fix_start_line=2, fix_end_line=3),
        note("F2", fixed_code="bad()", fix_start_line=4, fix_end_line=99),
    ]}
    merged, _ = run_merge(reply, [issue(line=1), issue(line=2)])
    assert (merged[0].ai.fixed_code, merged[0].ai.fix_start_line, merged[0].ai.fix_end_line) == ("ok()", 2, 3)
    assert merged[0].ai.fix == "use None"
    assert merged[1].ai is not None and merged[1].ai.fixed_code is None


@pytest.mark.parametrize("extra", [{"category": "style"}, {"category": "typo"}, {"severity": "urgent"}])
def test_rule3_style_and_unknown_values_are_dropped(extra):
    merged, _ = run_merge({"new_issues": [new(**extra)]}, [])
    assert merged == []


def test_rule4_critical_security_cannot_be_dismissed():
    critical = issue(category="security", severity="critical", tool="bandit")
    high_security = issue(line=2, category="security", severity="high", tool="bandit")
    reply = {"findings": [note("F1", "false_positive"), note("F2", "false_positive")]}
    merged, status = run_merge(reply, [critical, high_security])
    assert merged[0].ai.verdict == Verdict.CONFIRMED
    assert merged[1].is_false_positive  # only *critical* security is protected
    assert (status.overridden, status.confirmed, status.false_positives) == (1, 1, 1)


def test_rule5_ai_issues_are_capped_at_high():
    merged, _ = run_merge({"new_issues": [new(severity="critical")]}, [])
    assert merged[0].severity == "high"


def test_rule6_repeats_of_static_findings_and_each_other_are_dropped():
    reply = {"new_issues": [new(line=1), new(line=1, category="security"), new(line=4), new(line=4)]}
    merged, status = run_merge(reply, [issue(line=1, category="bug")])
    assert [(i.line, i.category.value) for i in merged[1:]] == [(1, "security"), (4, "bug")]
    assert status.added == 2


def test_rule6_new_issues_are_capped():
    reply = {"new_issues": [new(line=n) for n in range(1, 21)]}
    _, status = run_merge(reply, [], line_count=20)
    assert status.added == MAX_NEW_ISSUES


def test_rule7_bad_items_are_skipped_but_the_rest_kept():
    reply = {"findings": ["junk", None, note("F1")], "new_issues": [42, new(title=""), new(line=5)]}
    merged, status = run_merge(reply, [issue()])
    assert merged[0].ai is not None
    assert status.added == 1


@pytest.mark.parametrize("reply", [{"findings": "all good"}, {"new_issues": {"line": 1}}])
def test_rule7_wrong_overall_shape_raises(reply):
    with pytest.raises(LLMError, match="shape"):
        run_merge(reply, [])


def test_new_issue_fields():
    merged, _ = run_merge({"new_issues": [new(fix="init it", fixed_code="x = 0", fix_start_line=2, fix_end_line=2)]}, [])
    added = merged[0]
    assert (added.tool, added.rule_id, added.symbol, added.message) == ("ai", "ai-unbound-var", "unbound-var", "x may be unbound")
    assert (added.end_line, added.ai.verdict, added.ai.fixed_code) == (3, Verdict.CONFIRMED, "x = 0")


# --- review() end to end with a mocked LLM ---------------------------------------------------


def mock_client(reply: dict, seen: dict | None = None) -> LLMClient:
    def handler(request):
        if seen is not None:
            seen["body"] = json.loads(request.content)
        content = json.dumps(reply)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    settings = LLMSettings(provider="gemini", base_url="https://llm.test/v1", model="m", api_key="k")
    # sleep=no-op: retried 503s in these tests shouldn't really wait 2 s + 4 s.
    return LLMClient(settings, transport=httpx.MockTransport(handler), sleep=lambda seconds: None)


def test_info_findings_are_not_sent():
    seen = {}
    issues = [issue(line=1, severity="info", rule_id="INFO1"), issue(line=2, rule_id="REAL")]
    review("a\nb\n", PYTHON, issues, mock_client({}, seen))
    user = seen["body"]["messages"][1]["content"]
    assert "REAL" in user and "INFO1" not in user
    assert "F1: line 2" in user  # ids are assigned after filtering


def test_mocked_model_reports_the_process_logic_bug():
    # samples/buggy.py: process() returns `result`, which is unbound if int() raises (line 69).
    reply = {"new_issues": [new(line=69, end_line=69, rule="unbound-local", title="result may be unbound")]}
    merged, status = review(PROCESS_BUG_CODE, PYTHON, [], mock_client(reply))
    assert (merged[0].tool, merged[0].line, merged[0].rule_id) == ("ai", 69, "ai-unbound-local")
    assert (status.provider, status.model, status.added) == ("gemini", "m", 1)
