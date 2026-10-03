"""JSON: syntax errors and duplicate keys, using the standard library (no subprocess needed,
since json.loads only parses text into Python data and never executes anything)."""

import json
import re
from collections import Counter

from app.languages import LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "json"


def _key_line(code: str, key: str, occurrence: int) -> int:
    """Line of the n-th `"key":` in the text (best effort; falls back to line 1)."""
    pattern = re.compile(re.escape(json.dumps(key)) + r"\s*:")
    matches = list(pattern.finditer(code))
    if occurrence < len(matches):
        return code.count("\n", 0, matches[occurrence].start()) + 1
    return 1


def check(code: str) -> list[Issue]:
    duplicates: list[str] = []

    def collect_duplicates(pairs):
        seen = set()
        for key, _value in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        return dict(pairs)

    try:
        json.loads(code, object_pairs_hook=collect_duplicates)
    except json.JSONDecodeError as exc:
        hint = ""
        if "Expecting property name" in exc.msg or "Expecting value" in exc.msg:
            hint = " (JSON allows no comments or trailing commas)"
        return [
            Issue(
                tool=NAME,
                rule_id="syntax-error",
                category=Category.BUG,
                severity=Severity.HIGH,
                line=exc.lineno,
                message=f"Invalid JSON: {exc.msg}{hint}",
                symbol="syntax-error",
            )
        ]

    issues = []
    reported = Counter()
    for key in duplicates:
        reported[key] += 1
        issues.append(
            Issue(
                tool=NAME,
                rule_id="duplicate-key",
                category=Category.BUG,
                severity=Severity.MEDIUM,
                # The duplicate is the 2nd, 3rd, ... occurrence of the key in the text.
                line=_key_line(code, key, reported[key]),
                message=(
                    f'Duplicate key "{key}": most parsers keep only the last value, so the '
                    "earlier one is silently ignored."
                ),
                symbol="duplicate-key",
            )
        )
    return issues


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return check(code)
