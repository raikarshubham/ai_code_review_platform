"""Lizard: cyclomatic complexity for 20+ languages (everything with functions except Python,
which uses Radon). Same thresholds as Radon so scores are comparable across languages.
"""

import csv
import io

from app.analyzers.runner import AnalyzerError, run_tool
from app.languages import LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "lizard"

ARGS = ["--csv"]

COMPLEXITY_THRESHOLD = 10  # rank A/B (<= 10) is healthy
HIGH_COMPLEXITY = 20

# Lizard's --csv has no header. Columns, in order:
# NLOC, CCN, tokens, params, length, location, file, function, long_name, start, end
CCN, FUNCTION, START, END = 1, 7, 9, 10


def _rank(complexity: int) -> str:
    # Same rank letters as Radon: C 11-20, D 21-30, E 31-40, F 41+.
    for limit, rank in ((20, "C"), (30, "D"), (40, "E")):
        if complexity <= limit:
            return rank
    return "F"


def parse(output: str) -> list[Issue]:
    issues = []
    for row in csv.reader(io.StringIO(output)):
        if not row:
            continue
        try:
            complexity, start, end = int(row[CCN]), int(row[START]), int(row[END])
            name = row[FUNCTION]
        except (IndexError, ValueError) as exc:
            raise AnalyzerError(f"lizard returned an unexpected row: {row!r}") from exc
        if complexity <= COMPLEXITY_THRESHOLD:
            continue
        rank = _rank(complexity)
        issues.append(
            Issue(
                tool=NAME,
                rule_id=f"CC-{rank}",
                category=Category.COMPLEXITY,
                severity=Severity.HIGH if complexity > HIGH_COMPLEXITY else Severity.MEDIUM,
                line=start,
                end_line=end,
                message=(
                    f"'{name}' has cyclomatic complexity {complexity} (rank {rank}); "
                    f"consider splitting it into smaller functions"
                ),
                symbol="cyclomatic-complexity",
            )
        )
    return issues


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    # No functions in the file -> Lizard prints nothing, which is a valid "no issues".
    return parse(run_tool("lizard", ARGS, code, spec.temp_ext, allow_empty=True))
