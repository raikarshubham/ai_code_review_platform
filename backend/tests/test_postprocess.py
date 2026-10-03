from app.postprocess import dedupe, sort_issues
from app.schemas import Category, Issue, Severity


def make_issue(tool, rule_id, line, severity=Severity.MEDIUM, category=Category.BUG):
    return Issue(
        tool=tool, rule_id=rule_id, category=category, severity=severity,
        line=line, message=f"{tool} {rule_id}",
    )


def test_eval_reported_by_both_tools_becomes_one_issue():
    issues = [
        make_issue("pylint", "W0123", 32, Severity.HIGH, Category.SECURITY),
        make_issue("bandit", "B307", 32, Severity.HIGH, Category.SECURITY),
    ]
    result = dedupe(issues)
    assert len(result) == 1
    assert result[0].tool == "bandit"  # equal severity -> security specialist wins


def test_duplicate_keeps_higher_severity():
    issues = [
        make_issue("bandit", "B307", 5, Severity.MEDIUM, Category.SECURITY),
        make_issue("pylint", "W0123", 5, Severity.HIGH, Category.SECURITY),
    ]
    result = dedupe(issues)
    assert len(result) == 1
    assert result[0].severity == "high"


def test_too_many_branches_merges_with_radon():
    issues = [
        make_issue("pylint", "R0912", 72, Severity.LOW, Category.SMELL),
        make_issue("radon", "CC-C", 72, Severity.MEDIUM, Category.COMPLEXITY),
    ]
    result = dedupe(issues)
    assert [issue.tool for issue in result] == ["radon"]


def test_same_concept_on_different_lines_is_kept():
    issues = [
        make_issue("bandit", "B307", 10, Severity.HIGH, Category.SECURITY),
        make_issue("pylint", "W0123", 20, Severity.HIGH, Category.SECURITY),
    ]
    assert len(dedupe(issues)) == 2


def test_exact_duplicate_dropped_but_different_rules_kept():
    issues = [
        make_issue("pylint", "W0612", 3),
        make_issue("pylint", "W0612", 3),
        make_issue("pylint", "W0613", 3),
    ]
    assert sorted(issue.rule_id for issue in dedupe(issues)) == ["W0612", "W0613"]


def test_sort_by_severity_then_line():
    issues = [
        make_issue("pylint", "R1", 1, Severity.LOW),
        make_issue("bandit", "B1", 50, Severity.CRITICAL),
        make_issue("bandit", "B2", 10, Severity.CRITICAL),
        make_issue("pylint", "W1", 5, Severity.HIGH),
    ]
    assert [issue.rule_id for issue in sort_issues(issues)] == ["B2", "B1", "W1", "R1"]
