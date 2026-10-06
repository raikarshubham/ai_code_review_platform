"""Per-function complexity (the dashboard chart), with the real Radon and Lizard."""

from pathlib import Path

from app import metrics
from app.analyzers.runner import AnalyzerError
from app.languages import SPECS, Language
from app.pipeline import analyze

BUGGY_CODE = (Path(__file__).resolve().parent.parent / "samples" / "buggy.py").read_text(encoding="utf-8")

PYTHON = """\
def simple(x):
    return x


class Cart:
    def total(self, items):
        if not items:
            return 0
        return sum(items)
"""

JS = """\
function grade(score) {
  if (score > 90) return 'A';
  if (score > 80) return 'B';
  return 'C';
}
"""


def by_name(functions):
    return {f.name: f for f in functions}


def test_python_uses_radon_and_keeps_every_function():
    found = by_name(metrics.function_metrics(PYTHON, SPECS[Language.PYTHON]))
    assert set(found) == {"simple", "Cart.total"}
    assert (found["simple"].complexity, found["simple"].line) == (1, 1)
    assert (found["Cart.total"].complexity, found["Cart.total"].line) == (2, 6)


def test_other_languages_use_lizard():
    (grade,) = metrics.function_metrics(JS, SPECS[Language.JAVASCRIPT])
    assert (grade.name, grade.line, grade.end_line, grade.complexity) == ("grade", 1, 5, 3)


def test_languages_without_functions_have_none():
    assert metrics.function_metrics("SELECT 1;\n", SPECS[Language.SQL]) == []
    assert metrics.function_metrics("a: 1\n", SPECS[Language.YAML]) == []


def test_tool_failure_gives_no_metrics(monkeypatch):
    def broken(code, spec):
        raise AnalyzerError("radon crashed")

    monkeypatch.setattr(metrics.radon_runner, "run_raw", broken)
    assert metrics.function_metrics(PYTHON, SPECS[Language.PYTHON]) == []


def test_pipeline_returns_functions_matching_the_complexity_issue():
    result = analyze(BUGGY_CODE)
    functions = by_name(result.functions)
    assert functions["classify"].complexity == 11
    assert "process" in functions and functions["process"].complexity < 11
    (issue,) = [i for i in result.issues if i.tool == "radon"]
    # The chart and the issue come from the same parser, so they agree.
    assert f"complexity {functions['classify'].complexity}" in issue.message
    assert issue.line == functions["classify"].line
