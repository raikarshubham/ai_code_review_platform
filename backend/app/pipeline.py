"""Analysis pipeline: syntax check -> static analyzers (parallel) -> normalize -> score.

The LLM reviewer (Day 4) plugs in after the static analyzers without changing the API contract.
"""

import ast
from concurrent.futures import ThreadPoolExecutor

from app.analyzers import bandit_runner, pylint_runner
from app.analyzers.runner import AnalyzerError
from app.schemas import AnalyzeResponse, Category, Issue, Severity

# Each analyzer module exposes NAME and run(code) -> list[Issue].
ANALYZERS = [pylint_runner, bandit_runner]


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


def run_analyzers(code: str) -> tuple[list[Issue], dict[str, str]]:
    """Run every analyzer in parallel; a failing tool is reported, not fatal.

    Threads are enough here: each analyzer spends its time waiting on its own subprocess,
    so total latency is roughly the slowest tool instead of the sum of all of them.
    """
    issues: list[Issue] = []
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(ANALYZERS)) as pool:
        futures = {analyzer.NAME: pool.submit(analyzer.run, code) for analyzer in ANALYZERS}
        for name, future in futures.items():
            try:
                issues.extend(future.result())
            except AnalyzerError as exc:
                errors[name] = str(exc)
    return issues, errors


def summarize(issues: list[Issue]) -> dict[Severity, int]:
    counts = {severity: 0 for severity in Severity}
    for issue in issues:
        counts[issue.severity] += 1
    return counts


def analyze(code: str) -> AnalyzeResponse:
    syntax_issue = check_syntax(code)
    if syntax_issue:
        return AnalyzeResponse(issues=[syntax_issue], score=0, summary=summarize([syntax_issue]))

    issues, tool_errors = run_analyzers(code)

    # Placeholder score until the size-scaled scorer lands on Day 3.
    score = 100 if not issues else 50

    return AnalyzeResponse(
        issues=issues, score=score, summary=summarize(issues), tool_errors=tool_errors
    )
