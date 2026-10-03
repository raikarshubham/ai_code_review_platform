"""SQL, YAML, JSON and CSS analyzers: parsers on canned output plus real runs."""

import json

import pytest

from app.analyzers import css_runner, json_runner, sql_runner, yaml_runner
from app.analyzers.runner import AnalyzerError
from app.languages import SPECS, Language
from app.pipeline import ANALYZERS, analyze


def test_every_analyzer_name_in_the_language_table_is_registered():
    for spec in SPECS.values():
        for name in spec.analyzers:
            assert name in ANALYZERS, f"{spec.language.value} uses unknown analyzer {name!r}"


# --- SQL ----------------------------------------------------------------------------------


def sqlfluff_output(*violations):
    return json.dumps([{"filepath": "snippet.sql", "violations": list(violations)}])


def violation(code, line, description="d", name="n"):
    return {"code": code, "start_line_no": line, "end_line_no": line, "description": description, "name": name}


def test_sqlfluff_mapping():
    issues = sql_runner.parse(sqlfluff_output(
        violation("PRS", 3, "Found unparsable section"),
        violation("AM04", 1, "Query produces an unknown number of result columns."),
        violation("AL05", 2),
    ))
    by_rule = {issue.rule_id: issue for issue in issues}
    assert (by_rule["syntax-error"].category, by_rule["syntax-error"].severity) == ("bug", "high")
    assert (by_rule["AM04"].category, by_rule["AM04"].severity) == ("smell", "low")
    assert (by_rule["AL05"].category, by_rule["AL05"].severity) == ("style", "info")


def test_sqlfluff_no_violations():
    assert sql_runner.parse(sqlfluff_output()) == []


def test_sqlfluff_garbage_raises():
    with pytest.raises(AnalyzerError):
        sql_runner.parse("Traceback ...")


@pytest.mark.parametrize(
    ("sql", "lines"),
    [
        ("DELETE FROM orders;", [1]),
        ("SELECT 1;\nupdate users set active = false;\n", [2]),
        ("DELETE FROM orders WHERE id = 1;", []),
        ("UPDATE t SET a = 1 WHERE b = 2", []),
        # A WHERE inside a string or comment doesn't count.
        ("UPDATE t SET note = 'where';", [1]),
        ("DELETE FROM t -- WHERE id = 1\n;", [1]),
        ("-- DELETE FROM t;\nSELECT 1;", []),
    ],
)
def test_unbounded_writes(sql, lines):
    assert [issue.line for issue in sql_runner.unbounded_writes(sql)] == lines


def test_sql_pipeline_real():
    code = "SELECT * FROM users;\nDELETE FROM orders;\nSELEC name FROM t;\n"
    result = analyze(code, Language.SQL)
    assert result.tool_errors == {}
    rule_ids = {issue.rule_id for issue in result.issues}
    assert {"sql-unbounded-write", "AM04", "syntax-error"} <= rule_ids
    assert result.issues[0].rule_id in ("sql-unbounded-write", "syntax-error")  # high first


def test_clean_sql_scores_100():
    result = analyze("SELECT id, name FROM users WHERE id = 1;\n", Language.SQL)
    assert [issue for issue in result.issues if issue.severity != "info"] == []
    assert result.score == 100


# --- YAML ---------------------------------------------------------------------------------


def test_yamllint_mapping():
    output = (
        'snippet.yaml:3:1: [error] duplication of key "name" in mapping (key-duplicates)\n'
        "snippet.yaml:5:1: [error] syntax error: expected ',' or ']' (syntax)\n"
        "snippet.yaml:2:8: [warning] truthy value should be one of [false, true] (truthy)\n"
        "snippet.yaml:4:5: [error] trailing spaces (trailing-spaces)\n"
    )
    by_rule = {issue.rule_id: issue for issue in yaml_runner.parse(output)}
    assert (by_rule["key-duplicates"].severity, by_rule["key-duplicates"].line) == ("high", 3)
    assert by_rule["syntax-error"].category == "bug"
    assert (by_rule["truthy"].category, by_rule["truthy"].severity) == ("bug", "low")
    assert (by_rule["trailing-spaces"].category, by_rule["trailing-spaces"].severity) == ("style", "info")


def test_yamllint_garbage_raises():
    with pytest.raises(AnalyzerError):
        yaml_runner.parse("something unexpected")


def test_yaml_pipeline_real():
    code = "services:\n  web:\n    image: nginx:latest\n    privileged: true\nname: a\nname: b\n"
    result = analyze(code, Language.YAML)
    assert result.tool_errors == {}
    rule_ids = {issue.rule_id for issue in result.issues}
    assert {"key-duplicates", "yaml-privileged-container", "yaml-unpinned-image"} <= rule_ids


# --- JSON ---------------------------------------------------------------------------------


def test_json_valid_has_no_issues():
    assert json_runner.check('{"a": 1, "b": {"c": [1, 2]}}') == []


def test_json_trailing_comma():
    (issue,) = json_runner.check('{\n  "a": 1,\n}\n')
    # Python points at the comma itself and names the problem.
    assert (issue.rule_id, issue.severity, issue.line) == ("syntax-error", "high", 2)
    assert "trailing comma" in issue.message


def test_json_comment_gets_hint():
    (issue,) = json_runner.check('{\n  // a comment\n  "a": 1\n}\n')
    assert issue.line == 2
    assert "no comments" in issue.message


def test_json_duplicate_key_points_at_second_occurrence():
    (issue,) = json_runner.check('{\n  "port": 80,\n  "host": "x",\n  "port": 8080\n}')
    assert (issue.rule_id, issue.line, issue.severity) == ("duplicate-key", 4, "medium")


def test_json_pipeline_real():
    result = analyze('{\n  "password": "hunter2",\n  "port": 1,\n  "port": 2\n}\n', Language.JSON)
    assert result.tool_errors == {}
    assert {"json-hardcoded-secret", "duplicate-key"} <= {issue.rule_id for issue in result.issues}


# --- CSS ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("css", "expected"),
    [
        ("a { color: red; }", []),
        ("a { color red; }", [("parse-error", 1)]),
        ("a {}\n", [("empty-rule", 1)]),
        ("b {\n  color: red !important;\n}", [("important", 2)]),
        ("@media (max-width: 600px) {\n  a { color blue; }\n}", [("parse-error", 2)]),
        ("a { color: red; }\n}\nb { margin: 0; }", [("unbalanced-braces", 2)]),
        # The unclosed block also swallows the next rule, which then fails to parse.
        ("a { color: red;\nb { margin: 0 }", [("unbalanced-braces", 1), ("parse-error", 2)]),
        # Braces inside strings and comments don't count.
        ('a::after { content: "}"; }\n/* { */', []),
    ],
)
def test_css_checks(css, expected):
    assert sorted((issue.rule_id, issue.line) for issue in css_runner.check(css)) == sorted(expected)


def test_css_pipeline():
    result = analyze("a { color red; }\n.empty {}\n", Language.CSS)
    assert result.tool_errors == {}
    assert {issue.rule_id for issue in result.issues} == {"parse-error", "empty-rule"}
