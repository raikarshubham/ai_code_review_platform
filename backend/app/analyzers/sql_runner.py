"""SQL: sqlfluff (parse errors + structure lint) plus our own dangerous-statement checks.

Two analyzers live here so a sqlfluff failure doesn't hide our checks:
- `sqlfluff` (subprocess): parse errors and its non-cosmetic rules.
- `sql` (in-process, pure text): DELETE/UPDATE without WHERE, which sqlfluff doesn't check.
"""

import json
import re

from app.analyzers.runner import AnalyzerError, run_tool
from app.languages import LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "sqlfluff"

# ANSI is the portable default. Layout and capitalisation rules are pure formatting noise for a
# code-review tool (dozens of findings per query), so we exclude those rule groups.
ARGS = [
    "lint", "--format", "json", "--dialect", "ansi", "--nocolor",
    "--exclude-rules", "layout,capitalisation", "--processes", "1",
]

# sqlfluff rule-code prefix -> (category, severity).
GROUP_MAP: dict[str, tuple[Category, Severity]] = {
    "AM": (Category.SMELL, Severity.LOW),  # ambiguous (SELECT *, implicit joins, ...)
    "ST": (Category.SMELL, Severity.LOW),  # structure (unused CTEs, nested CASE, ...)
    "RF": (Category.SMELL, Severity.LOW),  # references (unqualified columns in joins, ...)
    "AL": (Category.STYLE, Severity.INFO),  # aliasing
    "CV": (Category.STYLE, Severity.INFO),  # conventions
}
SYNTAX_CODES = {"PRS", "TMP"}  # unparsable section / templating error


def parse(output: str) -> list[Issue]:
    try:
        files = json.loads(output)
        violations = files[0]["violations"] if files else []
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise AnalyzerError(f"sqlfluff returned unexpected output: {exc}") from exc

    issues = []
    for violation in violations:
        code = violation["code"]
        if code in SYNTAX_CODES:
            category, severity, rule_id = Category.BUG, Severity.HIGH, "syntax-error"
        else:
            category, severity = GROUP_MAP.get(code[:2], (Category.STYLE, Severity.INFO))
            rule_id = code
        issues.append(
            Issue(
                tool=NAME,
                rule_id=rule_id,
                category=category,
                severity=severity,
                line=violation["start_line_no"],
                end_line=violation.get("end_line_no"),
                message=violation["description"],
                symbol=violation.get("name") or rule_id,
            )
        )
    return issues


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return parse(run_tool(NAME, ARGS, code, spec.temp_ext, allow_empty=False))


# --- Our own checks (registered as the separate `sql` analyzer) ---------------------------

_COMMENT_OR_STRING = re.compile(r"--[^\n]*|/\*.*?\*/|'(?:[^']|'')*'", re.S)
_WRITE_STATEMENT = re.compile(r"^\s*(DELETE\s+FROM|UPDATE)\b", re.I)
_WHERE = re.compile(r"\bWHERE\b", re.I)


def _blank_out(match: re.Match) -> str:
    # Keep newlines so offsets still map to the right line numbers.
    return re.sub(r"[^\n]", " ", match.group(0))


def unbounded_writes(code: str) -> list[Issue]:
    """DELETE/UPDATE statements without a WHERE clause affect every row in the table."""
    # Blank out comments and string literals so a WHERE inside them doesn't count.
    text = _COMMENT_OR_STRING.sub(_blank_out, code)
    issues = []
    offset = 0
    for statement in text.split(";"):
        match = _WRITE_STATEMENT.match(statement)
        if match and not _WHERE.search(statement):
            keyword = " ".join(match.group(1).upper().split())
            issues.append(
                Issue(
                    tool="sql",
                    rule_id="sql-unbounded-write",
                    category=Category.BUG,
                    severity=Severity.HIGH,
                    line=text.count("\n", 0, offset + match.start(1)) + 1,
                    message=(
                        f"{keyword} without a WHERE clause changes every row in the table. "
                        "Add a WHERE condition (or use TRUNCATE if that's really intended)."
                    ),
                    symbol="unbounded-write",
                )
            )
        offset += len(statement) + 1  # +1 for the ';' removed by split
    return issues
