"""The prompt-evaluation harness: annotation parsing and scoring. No network."""

import pytest

from app.languages import Language
from app.pipeline import analyze
from app.schemas import AINote, AIReview, AnalyzeResponse, Issue
from evals.harness import ANNOTATION, load_snippet, load_snippets, score, totals


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def issue(line, category="bug", tool="ai", rule_id="ai-x", verdict=None, fixed_code=None, end_line=None):
    note = AINote(verdict=verdict, explanation="e", fixed_code=fixed_code) if verdict else None
    return Issue(tool=tool, rule_id=rule_id, category=category, severity="high", line=line,
                 end_line=end_line, message=f"issue at {line}", ai=note)


def response(*issues, error=None):
    return AnalyzeResponse(language=Language.PYTHON, issues=list(issues), score=50, summary={},
                           ai_review=AIReview(enabled=True, error=error))


SNIPPET = """\
# expect-fp: B105
TOKEN = "x"
# clean
def f(values):
    # expect: bug|smell
    # fix-must-not: sha256
    return values[len(values)]
"""


# --- Parsing --------------------------------------------------------------------------------


def test_annotations_are_removed_and_lines_remapped(tmp_path):
    snippet = load_snippet(write(tmp_path, "s.py", SNIPPET), "tuning")
    assert "expect" not in snippet.code and "clean" not in snippet.code  # never leak answers
    assert snippet.code.splitlines() == ['TOKEN = "x"', "def f(values):", "    return values[len(values)]"]
    assert [(e.kind, e.line, e.value) for e in snippet.expectations] == [
        ("fp", 1, "B105"), ("bug", 3, "bug|smell"), ("fix", 3, "sha256")]
    assert snippet.clean and snippet.language == Language.PYTHON


def test_c_style_comments_work(tmp_path):
    snippet = load_snippet(write(tmp_path, "s.go", "package p\n// expect: bug\nvar x = 1\n"), "heldout")
    assert [(e.kind, e.line) for e in snippet.expectations] == [("bug", 2)]


def test_annotation_without_code_after_it_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no code after"):
        load_snippet(write(tmp_path, "s.py", "x = 1\n# expect: bug\n"), "tuning")


def test_expect_fp_is_not_read_as_expect():
    assert ANNOTATION.match("# expect-fp: B105").groups() == ("expect-fp", "B105")


# --- Scoring --------------------------------------------------------------------------------


@pytest.fixture
def snippet(tmp_path):
    return load_snippet(write(tmp_path, "s.py", SNIPPET), "tuning")


def test_hit_within_tolerance_and_category(snippet):
    assert score(snippet, response(issue(5, category="smell", verdict="confirmed"))).found == 1  # 2 lines off
    assert score(snippet, response(issue(6, verdict="confirmed"))).found == 0  # 3 lines off
    assert score(snippet, response(issue(3, category="security", verdict="confirmed"))).found == 0  # wrong kind


def test_dismissed_issue_does_not_count_as_found(snippet):
    assert score(snippet, response(issue(3, verdict="false_positive"))).found == 0


def test_extras_are_ai_issues_nobody_expected(tmp_path):
    long_snippet = load_snippet(write(tmp_path, "s.py", "# expect: bug\nx = 1\n" + "y = 2\n" * 10), "tuning")
    result = score(long_snippet, response(
        issue(1, verdict="confirmed"),  # the expected bug
        issue(3, verdict="confirmed"),  # 2 lines away: same finding, not an extra
        issue(9, verdict="confirmed"),  # nobody expected this one
        issue(9, tool="pylint", rule_id="W1"),  # static findings are never extras
    ))
    assert result.extras == ["L9 ai:ai-x issue at 9"]


def test_planted_false_positive(snippet):
    b105 = dict(tool="bandit", rule_id="B105", category="security")
    assert score(snippet, response(issue(1, verdict="false_positive", **b105))).fp_correct == 1
    assert score(snippet, response(issue(1, verdict="confirmed", **b105))).fp_correct == 0


def test_dismissing_a_real_finding_is_counted(snippet):
    result = score(snippet, response(issue(3, tool="pylint", rule_id="W1", verdict="false_positive")))
    assert len(result.wrong_dismissals) == 1


def test_fix_checks(snippet):
    bad = score(snippet, response(issue(3, verdict="confirmed", fixed_code="hashlib.sha256(x)")))
    good = score(snippet, response(issue(3, verdict="confirmed", fixed_code="bcrypt.hashpw(x)")))
    inline = score(snippet, response(issue(3, verdict="confirmed", fixed_code="def f():\n    import os\n")))
    assert (len(bad.fix_violations), len(good.fix_violations)) == (1, 0)
    assert inline.fix_violations == ["L3 fix imports inside a function"]


def test_clean_file_with_ai_issues_is_a_violation(snippet):
    assert score(snippet, response(issue(3, verdict="confirmed"))).clean_violation
    assert not score(snippet, response(issue(3, tool="pylint", rule_id="W1"))).clean_violation


def test_totals():
    from evals.harness import SnippetScore

    scores = [SnippetScore("a", "tuning", expected=2, found=1, fp_total=1, fp_correct=1, seconds=2.0),
              SnippetScore("b", "tuning", expected=2, found=2, extras=["x"], error="boom", seconds=4.0)]
    result = totals(scores)
    assert (result["recall"], result["extras"], result["fp_dismissed"]) == (0.75, 1, "1/1")
    assert (result["errors"], result["avg_seconds"]) == (1, 3.0)


# --- The real snippet set -------------------------------------------------------------------


def test_snippet_set_shape():
    snippets = load_snippets()
    assert len(snippets) == 14
    assert sum(s.split == "heldout" for s in snippets) == 4
    for s in snippets:
        assert s.expectations or s.clean, f"{s.name} has no annotations"


@pytest.mark.parametrize("snippet", load_snippets(), ids=lambda s: s.name)
def test_every_snippet_analyzes_without_tool_errors(snippet):
    result = analyze(snippet.code, snippet.language)
    assert result.tool_errors == {}
    # Every planted false positive must actually be reported by the static tools.
    for exp in snippet.expectations:
        if exp.kind == "fp":
            assert any(i.rule_id == exp.value and i.line == exp.line for i in result.issues), exp
