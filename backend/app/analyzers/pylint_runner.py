"""Pylint: bugs and code smells."""

import json

from app.analyzers.runner import AnalyzerError, run_tool
from app.schemas import Category, Issue, Severity

NAME = "pylint"

DISABLED = [
    "C0114", "C0115", "C0116",  # missing docstrings: noise for pasted snippets
    "E0401",  # import-error: the user's dependencies aren't installed on our server
]

ARGS = ["--output-format=json", "--score=n", "--persistent=n", f"--disable={','.join(DISABLED)}"]

# Default mapping by Pylint message type.
TYPE_MAP: dict[str, tuple[Category, Severity]] = {
    "fatal": (Category.BUG, Severity.HIGH),
    "error": (Category.BUG, Severity.HIGH),
    "warning": (Category.BUG, Severity.MEDIUM),
    "refactor": (Category.SMELL, Severity.LOW),
    "convention": (Category.STYLE, Severity.INFO),
    "info": (Category.STYLE, Severity.INFO),
}

# Per-rule calibration (see CLAUDE.md "Severity calibration").
RULE_OVERRIDES: dict[str, tuple[Category, Severity]] = {
    "W0102": (Category.BUG, Severity.HIGH),  # mutable default argument: state shared across calls
    "W0702": (Category.BUG, Severity.HIGH),  # bare except: swallows KeyboardInterrupt/SystemExit
    "W0611": (Category.SMELL, Severity.LOW),  # unused import
    "W0612": (Category.SMELL, Severity.LOW),  # unused variable
    "W0613": (Category.SMELL, Severity.LOW),  # unused argument
    "W0123": (Category.SECURITY, Severity.HIGH),  # eval-used
    "W0122": (Category.SECURITY, Severity.HIGH),  # exec-used
}


def parse(output: str) -> list[Issue]:
    try:
        messages = json.loads(output)
    except json.JSONDecodeError as exc:
        raise AnalyzerError(f"pylint returned invalid JSON: {exc}") from exc

    issues = []
    for msg in messages:
        rule_id = msg["message-id"]
        category, severity = RULE_OVERRIDES.get(rule_id) or TYPE_MAP.get(
            msg["type"], (Category.SMELL, Severity.LOW)
        )
        issues.append(
            Issue(
                tool=NAME,
                rule_id=rule_id,
                category=category,
                severity=severity,
                line=max(msg["line"], 1),
                end_line=msg.get("endLine"),
                message=msg["message"],
                symbol=msg.get("symbol"),
            )
        )
    return issues


def run(code: str) -> list[Issue]:
    return parse(run_tool("pylint", ARGS, code))
