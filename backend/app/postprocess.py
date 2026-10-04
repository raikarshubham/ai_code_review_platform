"""Merge findings from several tools: drop duplicates, then sort most-severe first."""

from app.schemas import Category, Issue, Severity

# Lower number = more severe. Used for sorting and for picking the winner of a duplicate.
SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}

# Different tools' rule ids that describe the same underlying problem.
# Two issues with the same concept on the same line are one finding.
CONCEPTS = {
    ("pylint", "W0123"): "eval",
    ("bandit", "B307"): "eval",
    ("pylint", "W0122"): "exec",
    ("bandit", "B102"): "exec",
    # Pylint's too-many-branches and Radon both report branchy functions at the `def` line.
    ("pylint", "R0912"): "complexity",
}

# On equal severity, keep the specialist tool's version (its message is more specific).
PREFERRED_TOOL = {"eval": "bandit", "exec": "bandit", "complexity": "radon"}


def _concept(issue: Issue) -> str | None:
    if issue.tool == "radon" and issue.category == Category.COMPLEXITY:
        return "complexity"
    return CONCEPTS.get((issue.tool, issue.rule_id))


def _better(a: Issue, b: Issue, concept: str) -> Issue:
    if SEVERITY_RANK[a.severity] != SEVERITY_RANK[b.severity]:
        return a if SEVERITY_RANK[a.severity] < SEVERITY_RANK[b.severity] else b
    return b if b.tool == PREFERRED_TOOL.get(concept) else a


def dedupe(issues: list[Issue]) -> list[Issue]:
    kept: dict[tuple, Issue] = {}
    for issue in issues:
        concept = _concept(issue)
        if concept:
            key = ("concept", concept, issue.line)
            kept[key] = _better(kept[key], issue, concept) if key in kept else issue
        else:
            # Same tool + rule + line twice is an exact duplicate.
            kept.setdefault((issue.tool, issue.rule_id, issue.line), issue)
    return list(kept.values())


def sort_issues(issues: list[Issue]) -> list[Issue]:
    # False positives go last: still visible, but below everything that counts.
    return sorted(
        issues, key=lambda issue: (issue.is_false_positive, SEVERITY_RANK[issue.severity], issue.line, issue.tool)
    )
