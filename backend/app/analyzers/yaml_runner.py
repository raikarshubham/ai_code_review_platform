"""YAML: yamllint (syntax, duplicate keys, the YAML 1.1 "yes/no are booleans" trap)."""

import re

from app.analyzers.runner import AnalyzerError, run_tool
from app.languages import LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "yamllint"

# Default rules, minus the ones that are pure preference for pasted snippets.
CONFIG = (
    "{extends: default, rules: {"
    "document-start: disable, "
    "line-length: {max: 120, level: warning}, "
    "truthy: {check-keys: false}}}"
)
ARGS = ["-f", "parsable", "-d", CONFIG]

# snippet.yaml:3:1: [error] duplication of key "name" in mapping (key-duplicates)
LINE = re.compile(r"^.*?:(\d+):(\d+): \[(error|warning)\] (.*) \(([\w-]+)\)$")

RULE_MAP: dict[str, tuple[Category, Severity]] = {
    "syntax": (Category.BUG, Severity.HIGH),
    # The later key silently wins; the first value is lost.
    "key-duplicates": (Category.BUG, Severity.HIGH),
    "anchors": (Category.BUG, Severity.HIGH),  # alias to an undeclared anchor
    # `country: NO` parses as false in YAML 1.1 parsers (the "Norway problem").
    "truthy": (Category.BUG, Severity.LOW),
}


def parse(output: str) -> list[Issue]:
    issues = []
    for raw in output.splitlines():
        if not raw.strip():
            continue
        match = LINE.match(raw.strip())
        if match is None:
            raise AnalyzerError(f"yamllint returned an unexpected line: {raw!r}")
        line, _col, _level, message, rule = match.groups()
        category, severity = RULE_MAP.get(rule, (Category.STYLE, Severity.INFO))
        issues.append(
            Issue(
                tool=NAME,
                rule_id="syntax-error" if rule == "syntax" else rule,
                category=category,
                severity=severity,
                line=int(line),
                message=message,
                symbol=rule,
            )
        )
    return issues


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    # No problems -> yamllint prints nothing and exits 0.
    return parse(run_tool(NAME, ARGS, code, spec.temp_ext, allow_empty=True))
