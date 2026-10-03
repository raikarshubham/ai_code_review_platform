from app.schemas import Category, Issue, Severity
from app.scoring import count_loc, score


def issues_of(*severities):
    return [
        Issue(tool="t", rule_id=f"R{i}", category=Category.BUG, severity=s, line=1, message="m")
        for i, s in enumerate(severities)
    ]


def code_with_loc(n):
    return "\n".join(f"x{i} = {i}" for i in range(n))


def test_count_loc_ignores_blank_and_comment_lines():
    code = "# header\n\nx = 1\n    # indented comment\ny = 2  # trailing comment counts\n"
    assert count_loc(code) == 2


def test_no_issues_scores_100():
    assert score([], code_with_loc(10)) == 100


def test_small_file_penalty_is_unscaled():
    # 2 high (20) + 1 medium (4) + 1 low (1) = 25 penalty, file under 50 lines -> no discount
    issues = issues_of(Severity.HIGH, Severity.HIGH, Severity.MEDIUM, Severity.LOW)
    assert score(issues, code_with_loc(20)) == 75


def test_same_issues_score_higher_in_bigger_file():
    issues = issues_of(Severity.HIGH, Severity.HIGH, Severity.MEDIUM)
    small = score(issues, code_with_loc(20))
    big = score(issues, code_with_loc(800))  # sqrt(800/50) = 4 -> penalty 24 / 4 = 6
    assert big == 94
    assert big > small


def test_critical_caps_score_even_in_huge_file():
    assert score(issues_of(Severity.CRITICAL), code_with_loc(5000)) == 50


def test_score_floor_is_zero():
    assert score(issues_of(*[Severity.CRITICAL] * 10), code_with_loc(10)) == 0


def test_info_issues_are_free():
    assert score(issues_of(*[Severity.INFO] * 20), code_with_loc(10)) == 100
