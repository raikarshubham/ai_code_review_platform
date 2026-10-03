"""Analysis pipeline: static analyzers -> normalize -> AI review -> score.

Day 1 only does a syntax check. Pylint/Bandit (Day 2), Radon + scoring (Day 3) and the
LLM reviewer (Day 4) plug in here without changing the API contract.
"""

import ast

from app.schemas import AnalyzeResponse, Category, Issue, Severity


def check_syntax(code: str) -> Issue | None:
    """Return an Issue if the code doesn't parse, else None.

    ast.parse only builds a syntax tree; it never executes the code, so this is safe on
    untrusted input. Unparseable code can't be analyzed by the other tools anyway.
    """
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return Issue(
            tool="python",
            rule_id="syntax-error",
            category=Category.BUG,
            severity=Severity.HIGH,
            line=exc.lineno or 1,
            message=exc.msg,
            symbol="syntax-error",
        )
    return None


def summarize(issues: list[Issue]) -> dict[Severity, int]:
    counts = {severity: 0 for severity in Severity}
    for issue in issues:
        counts[issue.severity] += 1
    return counts


def analyze(code: str) -> AnalyzeResponse:
    syntax_issue = check_syntax(code)
    issues = [syntax_issue] if syntax_issue else []

    # Placeholder score until the real size-scaled scorer lands on Day 3.
    score = 0 if syntax_issue else 100

    return AnalyzeResponse(issues=issues, score=score, summary=summarize(issues))
