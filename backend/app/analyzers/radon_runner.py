"""Radon: cyclomatic complexity (number of independent paths through a function)."""

import json

from app.analyzers.runner import AnalyzerError, run_tool
from app.languages import LanguageSpec
from app.schemas import Category, FunctionMetric, Issue, Severity

NAME = "radon"

ARGS = ["cc", "-j"]

# Rank A (1-5) and B (6-10) are healthy, so we only report above 10.
COMPLEXITY_THRESHOLD = 10
HIGH_COMPLEXITY = 20  # rank D and above (21+) is hard to test and maintain


def _flatten(blocks: list[dict]) -> list[dict]:
    """Yield functions and methods, including nested closures.

    Radon lists each method twice (top level and inside its class's "methods"), so we skip
    class entries entirely. Nested functions only appear under "closures", so we recurse.
    """
    found = []
    for block in blocks:
        if block["type"] == "class":
            continue
        found.append(block)
        found.extend(_flatten(block.get("closures", [])))
    return found


def _blocks(output: str) -> list[dict]:
    try:
        report = json.loads(output)
        (file_result,) = report.values()  # exactly one file analyzed
    except (json.JSONDecodeError, AttributeError, ValueError) as exc:
        raise AnalyzerError(f"radon returned unexpected output: {exc}") from exc
    if isinstance(file_result, dict) and "error" in file_result:
        raise AnalyzerError(f"radon failed: {file_result['error']}")
    return _flatten(file_result)


def _name(block: dict) -> str:
    return f"{block['classname']}.{block['name']}" if block.get("classname") else block["name"]


def functions(output: str) -> list[FunctionMetric]:
    """Every function's complexity (the dashboard chart). parse() uses the same blocks, so the
    chart and the issue message always show the same number."""
    return [
        FunctionMetric(name=_name(block), line=block["lineno"], end_line=block.get("endline"),
                       complexity=block["complexity"])
        for block in _blocks(output)
    ]


def parse(output: str) -> list[Issue]:
    issues = []
    for block in _blocks(output):
        complexity = block["complexity"]
        if complexity <= COMPLEXITY_THRESHOLD:
            continue
        severity = Severity.HIGH if complexity > HIGH_COMPLEXITY else Severity.MEDIUM
        issues.append(
            Issue(
                tool=NAME,
                rule_id=f"CC-{block['rank']}",
                category=Category.COMPLEXITY,
                severity=severity,
                line=block["lineno"],
                end_line=block.get("endline"),
                message=(
                    f"'{_name(block)}' has cyclomatic complexity {complexity} (rank {block['rank']}); "
                    f"consider splitting it into smaller functions"
                ),
                symbol="cyclomatic-complexity",
            )
        )
    return issues


def run_raw(code: str, spec: LanguageSpec) -> str:
    return run_tool("radon", ARGS, code, spec.temp_ext)


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return parse(run_raw(code, spec))
