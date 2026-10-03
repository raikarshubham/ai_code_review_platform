"""Analysis pipeline: syntax check -> static analyzers (parallel) -> dedupe -> sort -> score.

Which analyzers run depends on the language (see app/languages.py). The LLM reviewer (Day 4)
plugs in after the static analyzers without changing the API contract.
"""

import ast
from concurrent.futures import ThreadPoolExecutor

from app.analyzers import bandit_runner, pylint_runner, radon_runner
from app.analyzers.runner import AnalyzerError
from app.languages import SPECS, Language, LanguageSpec
from app.postprocess import dedupe, sort_issues
from app.schemas import AnalyzeResponse, Category, Issue, Severity
from app.scoring import score

# Each analyzer module exposes NAME and run(code, spec) -> list[Issue].
ANALYZERS = {module.NAME: module for module in [pylint_runner, bandit_runner, radon_runner]}


def check_syntax(code: str) -> Issue | None:
    """Python only: return an Issue if the code doesn't parse, else None.

    Other languages get syntax errors from their analyzers (e.g. Semgrep parse errors).

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


def run_analyzers(code: str, spec: LanguageSpec) -> tuple[list[Issue], dict[str, str]]:
    """Run the language's analyzers in parallel; a failing tool is reported, not fatal.

    Threads are enough here: each analyzer spends its time waiting on its own subprocess,
    so total latency is roughly the slowest tool instead of the sum of all of them.
    """
    analyzers = [ANALYZERS[name] for name in spec.analyzers if name in ANALYZERS]
    issues: list[Issue] = []
    errors: dict[str, str] = {}
    if not analyzers:
        return issues, errors
    with ThreadPoolExecutor(max_workers=len(analyzers)) as pool:
        futures = {analyzer.NAME: pool.submit(analyzer.run, code, spec) for analyzer in analyzers}
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


def analyze(code: str, language: Language = Language.PYTHON) -> AnalyzeResponse:
    spec = SPECS[language]

    if language == Language.PYTHON:
        syntax_issue = check_syntax(code)
        if syntax_issue:
            return AnalyzeResponse(
                language=language, issues=[syntax_issue], score=0, summary=summarize([syntax_issue])
            )

    raw_issues, tool_errors = run_analyzers(code, spec)
    issues = sort_issues(dedupe(raw_issues))

    return AnalyzeResponse(
        language=language,
        issues=issues,
        score=score(issues, code, spec.comment_prefixes),
        summary=summarize(issues),
        tool_errors=tool_errors,
    )
