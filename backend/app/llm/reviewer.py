"""Ask the LLM to review the static findings, then validate and merge what it says.

Long files are split into chunks (app/llm/chunking.py) that are reviewed in parallel. Each
chunk's reply is validated on its own, then all chunks are combined.

The model's reply is untrusted input, exactly like the user's code. Each rule below exists
because a model can, and sometimes will, break it:

1. Verdicts for finding ids we never sent are dropped.
2. Line numbers outside the chunk that was sent (or end before start) are dropped.
3. Style issues and unknown categories or severities are dropped.
4. A critical security finding can never be dismissed as a false positive.
5. New AI issues are capped at high severity: "critical" (which caps the score at 50) is
   reserved for the deterministic tools.
6. New issues that repeat a static finding on the same line are dropped, and at most
   MAX_NEW_ISSUES are kept for the whole file.
7. A malformed item is dropped on its own; only a reply with the wrong overall shape fails.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.languages import LanguageSpec
from app.llm import chunking
from app.llm.chunking import Chunk
from app.llm.client import LLMClient, LLMError
from app.llm.prompt import build_messages
from app.schemas import AINote, AIReview, Category, Issue, Severity, Verdict

MAX_NEW_ISSUES = 15
NEW_ISSUE_CATEGORIES = {Category.BUG, Category.SECURITY, Category.SMELL, Category.COMPLEXITY}
# Parallel requests per review. Free tiers allow ~10-15 requests a minute, so a few at once
# speeds up long files without tripping the rate limit (and 429s are retried anyway).
MAX_PARALLEL = 3


@dataclass
class ChunkResult:
    """One chunk's validated reply."""

    notes: dict[int, AINote] = field(default_factory=dict)  # id(issue) -> note
    new_issues: list[Issue] = field(default_factory=list)
    overridden: int = 0


def review(code: str, spec: LanguageSpec, issues: list[Issue], client: LLMClient) -> tuple[list[Issue], AIReview]:
    lines = code.splitlines()
    chunk_plan = chunking.plan(code, spec)
    header = None
    if chunk_plan.header:
        header = "\n".join(lines[chunk_plan.header.start - 1 : chunk_plan.header.end])

    # Info-level findings (style notes, "imported subprocess") aren't worth free-tier tokens.
    sent = [issue for issue in issues if issue.severity != Severity.INFO]
    jobs = []
    for index, chunk in enumerate(chunk_plan.chunks):
        in_chunk = [issue for issue in sent if issue.line in chunk]
        findings = {f"F{number}": issue for number, issue in enumerate(in_chunk, start=1)}
        messages = build_messages(
            "\n".join(lines[chunk.start - 1 : chunk.end]),
            spec,
            findings,
            start_line=chunk.start,
            end_line=chunk.end,
            file_lines=len(lines),
            header=header if index > 0 else None,  # chunk 1 already contains the header
        )
        jobs.append((chunk, findings, messages))

    def run(job) -> ChunkResult:
        chunk, findings, messages = job
        return validate(client.chat_json(messages), findings, chunk)

    results: list[ChunkResult] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(jobs))) as pool:
        for future in [pool.submit(run, job) for job in jobs]:
            try:
                results.append(future.result())
            except LLMError as exc:
                errors.append(str(exc))

    if not results:
        # Nothing usable at all: same as before chunking, the pipeline reports the error.
        raise LLMError(errors[0] if len(jobs) == 1 else f"all {len(jobs)} chunks failed: {errors[0]}")

    merged, status = combine(issues, results)
    status.provider, status.model = client.settings.provider, client.settings.model
    status.chunks, status.truncated = len(jobs), chunk_plan.truncated
    if errors:
        # Partial result: the chunks that worked still count, findings in the others keep ai=None.
        status.error = f"{len(errors)} of {len(jobs)} chunks failed: {errors[0]}"
    return merged, status


def merge(
    reply: dict, issues: list[Issue], findings: dict[str, Issue], line_count: int
) -> tuple[list[Issue], AIReview]:
    """Validate one reply for a whole (unchunked) file and merge it. Pure: no I/O."""
    return combine(issues, [validate(reply, findings, Chunk(1, line_count))])


def validate(reply: dict, findings: dict[str, Issue], chunk: Chunk) -> ChunkResult:
    """Apply rules 1-5 and 7 to one chunk's reply. Pure: no I/O."""
    raw_findings = reply.get("findings", [])
    raw_new = reply.get("new_issues", [])
    if not isinstance(raw_findings, list) or not isinstance(raw_new, list):
        raise LLMError("model reply has the wrong shape: findings/new_issues must be lists")

    result = ChunkResult()
    for item in raw_findings:
        if not isinstance(item, dict) or item.get("id") not in findings:
            continue  # rule 1 (and 7)
        issue = findings[item["id"]]
        if id(issue) in result.notes:
            continue  # the model answered the same id twice; keep the first
        note = _note(item, chunk)
        if note is None:
            continue
        if note.verdict == Verdict.FALSE_POSITIVE and _is_critical_security(issue):
            note.verdict = Verdict.CONFIRMED  # rule 4
            result.overridden += 1
        result.notes[id(issue)] = note

    result.new_issues = [issue for issue in (_new_issue(item, chunk) for item in raw_new) if issue]
    return result


def combine(issues: list[Issue], results: list[ChunkResult]) -> tuple[list[Issue], AIReview]:
    """Merge validated chunk results into the issue list and apply rule 6 across all chunks."""
    notes = {key: note for result in results for key, note in result.notes.items()}
    merged = [issue.model_copy(update={"ai": notes[id(issue)]}) if id(issue) in notes else issue for issue in issues]

    status = AIReview(enabled=True, overridden=sum(result.overridden for result in results))
    status.confirmed = sum(1 for note in notes.values() if note.verdict == Verdict.CONFIRMED)
    status.false_positives = len(notes) - status.confirmed

    taken = {(issue.line, issue.category) for issue in issues}
    for new_issue in (issue for result in results for issue in result.new_issues):
        if (new_issue.line, new_issue.category) in taken:
            continue  # rule 6
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


def _line(value, chunk: Chunk) -> int | None:
    # bool is a subclass of int in Python, so `true` would otherwise pass as line 1.
    if isinstance(value, int) and not isinstance(value, bool) and value in chunk:
        return value
    return None


def _note(item: dict, chunk: Chunk) -> AINote | None:
    explanation = _text(item.get("explanation"))
    if explanation is None or item.get("verdict") not in {v.value for v in Verdict}:
        return None
    note = AINote(verdict=item["verdict"], explanation=explanation, fix=_text(item.get("fix")))

    # fixed_code is only kept with a valid line range to replace (rule 2).
    fixed_code = item.get("fixed_code")
    start = _line(item.get("fix_start_line"), chunk)
    end = _line(item.get("fix_end_line"), chunk)
    if isinstance(fixed_code, str) and fixed_code.strip() and start and end and start <= end:
        note.fixed_code, note.fix_start_line, note.fix_end_line = fixed_code, start, end
    return note


def _new_issue(item, chunk: Chunk) -> Issue | None:
    if not isinstance(item, dict):
        return None
    line = _line(item.get("line"), chunk)
    if line is None:
        return None  # rule 2
    end_line = line if item.get("end_line") is None else _line(item.get("end_line"), chunk)
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
    note = _note({**item, "verdict": Verdict.CONFIRMED.value}, chunk)
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
