"""Analysis pipeline: syntax check -> static analyzers (parallel) -> dedupe -> AI review -> sort -> score.

Which analyzers run depends on the language (see app/languages.py). The AI review is optional
and can fail on its own: the static results are always returned.
"""

import ast
from concurrent.futures import ThreadPoolExecutor

from app.analyzers import (
    bandit_runner,
    css_runner,
    json_runner,
    lizard_runner,
    pylint_runner,
    radon_runner,
    semgrep_runner,
    sql_checks,
    sql_runner,
    yaml_runner,
)
from app.analyzers.runner import AnalyzerError
from app.languages import SPECS, Language, LanguageSpec
from app.llm.client import LLMClient, LLMError
from app.llm.reviewer import review
from app.postprocess import dedupe, sort_issues
from app.schemas import AIReview, AnalyzeResponse, Category, Issue, Severity
from app.scoring import score

# Each analyzer module exposes NAME and run(code, spec) -> list[Issue].
ANALYZERS = {
    module.NAME: module
    for module in [
        pylint_runner, bandit_runner, radon_runner,  # Python
        lizard_runner, semgrep_runner,  # most other languages
        sql_runner, sql_checks, yaml_runner, json_runner, css_runner,  # SQL and data/markup
    ]
}


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
    analyzers = [ANALYZERS[name] for name in spec.analyzers]
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


def ai_review_step(
    code: str, spec: LanguageSpec, issues: list[Issue], client: LLMClient | None
) -> tuple[list[Issue], AIReview]:
    """Run the LLM reviewer. If it fails, keep the static issues and say why in ai_review.error."""
    if client is None:
        return issues, AIReview()
    try:
        return review(code, spec, issues, client)
    except LLMError as exc:
        settings = client.settings
        return issues, AIReview(enabled=True, provider=settings.provider, model=settings.model, error=str(exc))


def analyze(code: str, language: Language = Language.PYTHON, llm_client: LLMClient | None = None) -> AnalyzeResponse:
    spec = SPECS[language]

    if language == Language.PYTHON:
        syntax_issue = check_syntax(code)
        if syntax_issue:
            return AnalyzeResponse(
                language=language, issues=[syntax_issue], score=0, summary=summarize([syntax_issue])
            )

    raw_issues, tool_errors = run_analyzers(code, spec)
    issues, ai_status = ai_review_step(code, spec, dedupe(raw_issues), llm_client)
    issues = sort_issues(issues)

    # False positives stay in the response, so the user sees what was dismissed and why, but
    # they don't cost points.
    counted = [issue for issue in issues if not issue.is_false_positive]
    return AnalyzeResponse(
        language=language,
        issues=issues,
        score=score(counted, code, spec.comment_prefixes),
        summary=summarize(counted),
        tool_errors=tool_errors,
        ai_review=ai_status,
    )
