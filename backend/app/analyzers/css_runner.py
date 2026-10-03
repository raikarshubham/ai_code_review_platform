"""CSS: parse errors (tinycss2), unbalanced braces, empty rules and !important.

CSS is deliberately error-tolerant: browsers silently drop what they can't parse, so these
"errors" don't crash anything, they just make styles quietly not apply. Hence medium, not high.
tinycss2 only tokenizes and parses the text; nothing is executed.
"""

import re

import tinycss2

from app.languages import LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "css"

NESTED_AT_RULES = {"media", "supports", "layer", "container", "document"}

_COMMENT_OR_STRING = re.compile(r"/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.S)


def _issue(rule_id, category, severity, line, message) -> Issue:
    return Issue(
        tool=NAME, rule_id=rule_id, category=category, severity=severity,
        line=max(line or 1, 1), message=message, symbol=rule_id,
    )


def _parse_error(line: int) -> Issue:
    # tinycss2's own messages contain an unformatted placeholder, so we write our own.
    return _issue(
        "parse-error", Category.BUG, Severity.MEDIUM, line,
        "Invalid declaration (expected `property: value;`). Browsers silently drop it.",
    )


def _check_rules(nodes) -> list[Issue]:
    issues = []
    for node in nodes:
        if node.type == "error":
            issues.append(_parse_error(node.source_line))
        elif node.type == "qualified-rule":
            declarations = tinycss2.parse_declaration_list(
                node.content, skip_comments=True, skip_whitespace=True
            )
            if not declarations:
                issues.append(_issue(
                    "empty-rule", Category.SMELL, Severity.LOW, node.source_line,
                    "Empty rule: it has no declarations and can be removed.",
                ))
            for declaration in declarations:
                if declaration.type == "error":
                    issues.append(_parse_error(declaration.source_line))
                elif declaration.type == "declaration" and declaration.important:
                    issues.append(_issue(
                        "important", Category.SMELL, Severity.LOW, declaration.source_line,
                        f"!important on '{declaration.name}' overrides the cascade and makes "
                        "styles hard to change later. Prefer a more specific selector.",
                    ))
        elif node.type == "at-rule" and node.lower_at_keyword in NESTED_AT_RULES and node.content:
            issues.extend(_check_rules(
                tinycss2.parse_rule_list(node.content, skip_comments=True, skip_whitespace=True)
            ))
    return issues


def unbalanced_braces(code: str) -> list[Issue]:
    """tinycss2 auto-closes blocks at end of input and swallows stray '}', so check ourselves."""
    text = _COMMENT_OR_STRING.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), code)
    open_lines: list[int] = []
    issues = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for char in line:
            if char == "{":
                open_lines.append(line_number)
            elif char == "}":
                if open_lines:
                    open_lines.pop()
                else:
                    issues.append(_issue(
                        "unbalanced-braces", Category.BUG, Severity.MEDIUM, line_number,
                        "Unmatched '}': the next rule's selector will be broken.",
                    ))
    for line_number in open_lines:
        issues.append(_issue(
            "unbalanced-braces", Category.BUG, Severity.MEDIUM, line_number,
            "'{' is never closed: every rule after it is swallowed into this block.",
        ))
    return issues


def check(code: str) -> list[Issue]:
    rules = tinycss2.parse_stylesheet(code, skip_comments=True, skip_whitespace=True)
    return _check_rules(rules) + unbalanced_braces(code)


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return check(code)
