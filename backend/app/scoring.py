"""Turn a list of issues into a 0-100 quality score, scaled by code size.

    penalty = sum of severity weights
    size    = max(1, sqrt(loc / 50))     # files up to 50 lines get no discount
    score   = 100 - penalty / size       # clamped to 0..100
    any critical issue caps the score at 50

Why sqrt: a bigger file with the same issues is better code, but not proportionally better.
Ten issues in 500 lines beat ten issues in 20 lines, just not by 25x.
Why the cap: a single SQL injection shouldn't be diluted away by a large file.
"""

import math

from app.schemas import Issue, Severity

SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 10,
    Severity.MEDIUM: 4,
    Severity.LOW: 1,
    Severity.INFO: 0,  # style/convention notes shouldn't lower the score
}

BASELINE_LOC = 50
CRITICAL_CAP = 50


def count_loc(code: str) -> int:
    """Non-blank lines that aren't just a comment."""
    return sum(
        1 for line in code.splitlines() if line.strip() and not line.strip().startswith("#")
    )


def score(issues: list[Issue], code: str) -> int:
    penalty = sum(SEVERITY_WEIGHTS[issue.severity] for issue in issues)
    size_factor = max(1.0, math.sqrt(count_loc(code) / BASELINE_LOC))
    result = round(100 - penalty / size_factor)
    result = max(0, min(100, result))
    if any(issue.severity == Severity.CRITICAL for issue in issues):
        result = min(result, CRITICAL_CAP)
    return result
