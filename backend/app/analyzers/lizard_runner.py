"""Lizard: cyclomatic complexity for 20+ languages (everything with functions except Python,
which uses Radon). Same thresholds as Radon so scores are comparable across languages.
"""

import csv
import io

from app.analyzers.runner import AnalyzerError, run_tool
from app.languages import LanguageSpec
from app.schemas import Category, FunctionMetric, Issue, Severity

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


def functions(output: str) -> list[FunctionMetric]:
    """Every function Lizard found, with its complexity. One parser for the issues (parse), the
    dashboard chart and the AI chunker (function_ranges), so they can never disagree."""
    found = []
    for row in csv.reader(io.StringIO(output)):
        if not row:
            continue
        try:
            found.append(
                FunctionMetric(name=row[FUNCTION], line=int(row[START]), end_line=int(row[END]),
                               complexity=int(row[CCN]))
            )
        except (IndexError, ValueError) as exc:
            raise AnalyzerError(f"lizard returned an unexpected row: {row!r}") from exc
    return found


def parse(output: str) -> list[Issue]:
    issues = []
    for function in functions(output):
        if function.complexity <= COMPLEXITY_THRESHOLD:
            continue
        rank = _rank(function.complexity)
        issues.append(
            Issue(
                tool=NAME,
                rule_id=f"CC-{rank}",
                category=Category.COMPLEXITY,
                severity=Severity.HIGH if function.complexity > HIGH_COMPLEXITY else Severity.MEDIUM,
                line=function.line,
                end_line=function.end_line,
                message=(
                    f"'{function.name}' has cyclomatic complexity {function.complexity} (rank {rank}); "
                    f"consider splitting it into smaller functions"
                ),
                symbol="cyclomatic-complexity",
            )
        )
    return issues


def run_raw(code: str, spec: LanguageSpec) -> str:
    # No functions in the file -> Lizard prints nothing, which is a valid empty result.
    return run_tool("lizard", ARGS, code, spec.temp_ext, allow_empty=True)


def function_ranges(code: str, spec: LanguageSpec) -> list[tuple[int, int]]:
    """(start, end) line of every function Lizard finds. The AI reviewer uses these to split
    long files at function boundaries. Raises AnalyzerError like run()."""
    return [(function.line, function.end_line) for function in functions(run_raw(code, spec))]


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return parse(run_raw(code, spec))
