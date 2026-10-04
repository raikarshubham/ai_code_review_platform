"""Ask the LLM to review the static findings, then validate and merge what it says.

The model's reply is untrusted input, exactly like the user's code. Each rule below exists
because a model can, and sometimes will, break it:

1. Verdicts for finding ids we never sent are dropped.
2. Line numbers outside the file (or end before start) are dropped.
3. Style issues and unknown categories or severities are dropped.
4. A critical security finding can never be dismissed as a false positive.
5. New AI issues are capped at high severity: "critical" (which caps the score at 50) is
   reserved for the deterministic tools.
6. New issues that repeat a static finding on the same line are dropped, and at most
   MAX_NEW_ISSUES are kept.
7. A malformed item is dropped on its own; only a reply with the wrong overall shape fails.
"""

import re

from app.languages import LanguageSpec
from app.llm.client import LLMClient, LLMError
from app.llm.prompt import build_messages
from app.schemas import AINote, AIReview, Category, Issue, Severity, Verdict

MAX_NEW_ISSUES = 15
NEW_ISSUE_CATEGORIES = {Category.BUG, Category.SECURITY, Category.SMELL, Category.COMPLEXITY}


def review(code: str, spec: LanguageSpec, issues: list[Issue], client: LLMClient) -> tuple[list[Issue], AIReview]:
    # Info-level findings (style notes, "imported subprocess") aren't worth free-tier tokens.
    sent = [issue for issue in issues if issue.severity != Severity.INFO]
    findings = {f"F{number}": issue for number, issue in enumerate(sent, start=1)}
    reply = client.chat_json(build_messages(code, spec, findings))
    merged, status = merge(reply, issues, findings, line_count=len(code.splitlines()))
    status.provider, status.model = client.settings.provider, client.settings.model
    return merged, status


def merge(
    reply: dict, issues: list[Issue], findings: dict[str, Issue], line_count: int
) -> tuple[list[Issue], AIReview]:
    """Apply the model's verdicts to `issues` and append its new issues. Pure: no I/O."""
    raw_findings = reply.get("findings", [])
    raw_new = reply.get("new_issues", [])
    if not isinstance(raw_findings, list) or not isinstance(raw_new, list):
        raise LLMError("model reply has the wrong shape: findings/new_issues must be lists")

    status = AIReview(enabled=True)
    notes: dict[int, AINote] = {}  # id(issue) -> note; issues are pydantic models, not hashable
    for item in raw_findings:
        if not isinstance(item, dict) or item.get("id") not in findings:
            continue  # rule 1 (and 7)
        issue = findings[item["id"]]
        if id(issue) in notes:
            continue  # the model answered the same id twice; keep the first
        note = _note(item, line_count)
        if note is None:
            continue
        if note.verdict == Verdict.FALSE_POSITIVE and _is_critical_security(issue):
            note.verdict = Verdict.CONFIRMED  # rule 4
            status.overridden += 1
        notes[id(issue)] = note

    merged = [issue.model_copy(update={"ai": notes[id(issue)]}) if id(issue) in notes else issue for issue in issues]
    status.confirmed = sum(1 for note in notes.values() if note.verdict == Verdict.CONFIRMED)
    status.false_positives = len(notes) - status.confirmed

    taken = {(issue.line, issue.category) for issue in issues}
    for item in raw_new:
        new_issue = _new_issue(item, line_count)
        if new_issue is None or (new_issue.line, new_issue.category) in taken:
            continue  # rules 2, 3, 6
        taken.add((new_issue.line, new_issue.category))
        merged.append(new_issue)
        status.added += 1
        if status.added == MAX_NEW_ISSUES:
            break
    return merged, status


def _is_critical_security(issue: Issue) -> bool:
    return issue.severity == Severity.CRITICAL and issue.category == Category.SECURITY


def _text(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _line(value, line_count: int) -> int | None:
    # bool is a subclass of int in Python, so `true` would otherwise pass as line 1.
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= line_count:
        return value
    return None


def _note(item: dict, line_count: int) -> AINote | None:
    explanation = _text(item.get("explanation"))
    if explanation is None or item.get("verdict") not in {v.value for v in Verdict}:
        return None
    note = AINote(verdict=item["verdict"], explanation=explanation, fix=_text(item.get("fix")))

    # fixed_code is only kept with a valid line range to replace (rule 2).
    fixed_code = item.get("fixed_code")
    start = _line(item.get("fix_start_line"), line_count)
    end = _line(item.get("fix_end_line"), line_count)
    if isinstance(fixed_code, str) and fixed_code.strip() and start and end and start <= end:
        note.fixed_code, note.fix_start_line, note.fix_end_line = fixed_code, start, end
    return note


def _new_issue(item, line_count: int) -> Issue | None:
    if not isinstance(item, dict):
        return None
    line = _line(item.get("line"), line_count)
    if line is None:
        return None  # rule 2
    end_line = line if item.get("end_line") is None else _line(item.get("end_line"), line_count)
    if end_line is None or end_line < line:
        return None  # rule 2

    try:
        category, severity = Category(item.get("category")), Severity(item.get("severity"))
    except ValueError:
        return None  # rule 3
    if category not in NEW_ISSUE_CATEGORIES:
        return None  # rule 3: style
    if severity == Severity.CRITICAL:
        severity = Severity.HIGH  # rule 5

    title = _text(item.get("title"))
    note = _note({**item, "verdict": Verdict.CONFIRMED.value}, line_count)
    if title is None or note is None:
        return None

    slug = re.sub(r"[^a-z0-9]+", "-", str(item.get("rule", "")).lower()).strip("-")[:40] or "finding"
    return Issue(
        tool="ai",
        rule_id=f"ai-{slug}",
        category=category,
        severity=severity,
        line=line,
        end_line=end_line,
        message=title,
        symbol=slug,
        ai=note,
    )
