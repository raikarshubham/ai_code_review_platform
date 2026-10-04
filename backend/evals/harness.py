"""Score the AI review against snippets whose expected answers are written in comments.

Annotations (same idea as the Semgrep rule fixtures), on the line(s) above the code they mean:
    # expect: bug          an issue of this category (or bug|smell) must be reported near here
    # expect-fp: B105      the static finding with this rule id here is a false positive
    # fix-must-not: sha256 the fixed_code for the issue here must not contain this text
    # clean                (anywhere) the AI should add no new issues to this file
`//` works instead of `#` for C-style languages.

The annotation lines are REMOVED before the code is analyzed: the expected answers must never
be part of the model's input. Expected line numbers refer to the cleaned code.
"""

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.languages import Language, detect_language
from app.schemas import AnalyzeResponse, Issue

SNIPPETS_DIR = Path(__file__).resolve().parent / "snippets"
SPLITS = ("tuning", "heldout")
TOLERANCE = 2  # an issue within 2 lines of the expected line counts as a hit

ANNOTATION = re.compile(r"^\s*(?:#|//)\s*(expect-fp|expect|fix-must-not|clean)\b:?\s*(.*?)\s*$")
KINDS = {"expect": "bug", "expect-fp": "fp", "fix-must-not": "fix"}
# An import indented inside a function in fixed_code: imports belong at the top of the file.
INLINE_IMPORT = re.compile(r"^[ \t]+(import |from \S+ import )", re.MULTILINE)


@dataclass(frozen=True)
class Expectation:
    kind: str  # "bug", "fp" or "fix"
    line: int  # in the cleaned code
    value: str  # categories ("bug|smell"), a rule id, or forbidden fix text


@dataclass
class Snippet:
    name: str
    split: str
    language: Language
    code: str  # annotations removed
    expectations: list[Expectation]
    clean: bool


@dataclass
class SnippetScore:
    name: str
    split: str
    expected: int = 0
    found: int = 0
    missed: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)  # AI issues no expectation asked for
    fp_total: int = 0
    fp_correct: int = 0
    wrong_dismissals: list[str] = field(default_factory=list)  # real findings marked false positive
    fix_violations: list[str] = field(default_factory=list)
    clean_violation: bool = False
    seconds: float | None = None
    error: str | None = None  # ai_review.error


def load_snippet(path: Path, split: str) -> Snippet:
    language = detect_language(path.name)
    if language is None:
        raise ValueError(f"{path.name}: unknown language")
    lines, expectations, pending, clean = [], [], [], False
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = ANNOTATION.match(raw)
        if match:
            kind, value = match.groups()
            if kind == "clean":
                clean = True
            else:
                pending.append((KINDS[kind], value))
            continue
        lines.append(raw)
        if pending and raw.strip():
            expectations += [Expectation(kind, len(lines), value) for kind, value in pending]
            pending = []
    if pending:
        raise ValueError(f"{path.name}: annotation with no code after it")
    return Snippet(path.stem, split, language, "\n".join(lines) + "\n", expectations, clean)


def load_snippets(which: str = "all") -> list[Snippet]:
    splits = SPLITS if which == "all" else (which,)
    return [
        load_snippet(path, split)
        for split in splits
        for path in sorted((SNIPPETS_DIR / split).iterdir())
        if path.is_file()
    ]


def _near(issue: Issue, line: int) -> bool:
    return issue.line - TOLERANCE <= line <= (issue.end_line or issue.line) + TOLERANCE


def _label(issue: Issue) -> str:
    return f"L{issue.line} {issue.tool}:{issue.rule_id} {issue.message[:50]}"


def score(snippet: Snippet, response: AnalyzeResponse, seconds: float | None = None) -> SnippetScore:
    result = SnippetScore(snippet.name, snippet.split, seconds=seconds, error=response.ai_review.error)
    counted = [issue for issue in response.issues if not issue.is_false_positive]
    bug_lines = [exp.line for exp in snippet.expectations if exp.kind == "bug"]

    for exp in snippet.expectations:
        if exp.kind == "bug":
            result.expected += 1
            categories = exp.value.split("|")
            if any(_near(issue, exp.line) and issue.category.value in categories for issue in counted):
                result.found += 1
            else:
                result.missed.append(f"L{exp.line} {exp.value}")
        elif exp.kind == "fp":
            result.fp_total += 1
            planted = [i for i in response.issues if i.rule_id == exp.value and _near(i, exp.line)]
            if any(issue.is_false_positive for issue in planted):
                result.fp_correct += 1
        elif exp.kind == "fix":
            for issue in counted:
                code = issue.ai.fixed_code if issue.ai else None
                if code and _near(issue, exp.line) and exp.value.lower() in code.lower():
                    result.fix_violations.append(f"L{exp.line} fix contains {exp.value!r}")

    planted_fps = {(exp.value, exp.line) for exp in snippet.expectations if exp.kind == "fp"}
    for issue in response.issues:
        if issue.is_false_positive and not any(rule == issue.rule_id and _near(issue, line) for rule, line in planted_fps):
            result.wrong_dismissals.append(_label(issue))
        if issue.ai and issue.ai.fixed_code and INLINE_IMPORT.search(issue.ai.fixed_code):
            result.fix_violations.append(f"L{issue.line} fix imports inside a function")

    ai_issues = [issue for issue in counted if issue.tool == "ai"]
    result.extras = [_label(issue) for issue in ai_issues if not any(_near(issue, line) for line in bug_lines)]
    result.clean_violation = snippet.clean and bool(ai_issues)
    return result


def totals(scores: list[SnippetScore]) -> dict:
    expected = sum(s.expected for s in scores)
    fp_total = sum(s.fp_total for s in scores)
    return {
        "snippets": len(scores),
        "recall": round(sum(s.found for s in scores) / expected, 3) if expected else None,
        "found": sum(s.found for s in scores),
        "expected": expected,
        "extras": sum(len(s.extras) for s in scores),
        "fp_dismissed": f"{sum(s.fp_correct for s in scores)}/{fp_total}",
        "wrong_dismissals": sum(len(s.wrong_dismissals) for s in scores),
        "fix_violations": sum(len(s.fix_violations) for s in scores),
        "clean_violations": sum(s.clean_violation for s in scores),
        "errors": sum(s.error is not None for s in scores),
        "avg_seconds": round(sum(s.seconds or 0 for s in scores) / len(scores), 1) if scores else None,
    }


def as_dict(score_: SnippetScore) -> dict:
    return asdict(score_)
