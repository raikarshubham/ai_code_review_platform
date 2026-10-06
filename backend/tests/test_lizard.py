import pytest

from app.analyzers import lizard_runner
from app.analyzers.runner import AnalyzerError
from app.languages import SPECS, Language
from app.pipeline import analyze

# 12 independent branches -> CCN 13 (rank C).
BRANCHY_JS = "function grade(s) {\n" + "".join(
    f"  if (s === {i}) {{ return {i}; }}\n" for i in range(12)
) + "  return -1;\n}\n"


def csv_row(name, ccn, start, end):
    return f'5,{ccn},40,1,{end - start + 1},"{name}@{start}-{end}@f.js","f.js","{name}","{name}( x )",{start},{end}\n'


def test_parse_reports_only_above_threshold():
    output = csv_row("simple", 3, 1, 4) + csv_row("edge", 10, 5, 9) + csv_row("branchy", 13, 10, 30)
    issues = lizard_runner.parse(output)
    assert len(issues) == 1
    issue = issues[0]
    assert (issue.category, issue.severity, issue.rule_id) == ("complexity", "medium", "CC-C")
    assert (issue.line, issue.end_line) == (10, 30)
    assert "'branchy'" in issue.message


@pytest.mark.parametrize(("ccn", "rank", "severity"), [(21, "D", "high"), (35, "E", "high"), (50, "F", "high")])
def test_parse_ranks(ccn, rank, severity):
    issue = lizard_runner.parse(csv_row("f", ccn, 1, 2))[0]
    assert (issue.rule_id, issue.severity) == (f"CC-{rank}", severity)


def test_functions_lists_every_function():
    output = csv_row("simple", 3, 1, 4) + csv_row("branchy", 13, 10, 30)
    found = [(f.name, f.line, f.end_line, f.complexity) for f in lizard_runner.functions(output)]
    assert found == [("simple", 1, 4, 3), ("branchy", 10, 30, 13)]
    assert lizard_runner.functions("") == []


def test_parse_empty_output_means_no_functions():
    assert lizard_runner.parse("") == []


def test_parse_garbage_raises():
    with pytest.raises(AnalyzerError):
        lizard_runner.parse("not,a,lizard,row\n")


# --- Real tool ---------------------------------------------------------------------------


def test_real_lizard_flags_branchy_javascript():
    issues = lizard_runner.run(BRANCHY_JS, SPECS[Language.JAVASCRIPT])
    assert len(issues) == 1
    assert "'grade'" in issues[0].message
    assert issues[0].line == 1


def test_real_lizard_file_without_functions():
    assert lizard_runner.run("// just a comment\n", SPECS[Language.JAVASCRIPT]) == []


@pytest.mark.parametrize(
    ("language", "code"),
    [
        (Language.GO, "func f(x int) int {\n" + "".join(f"  if x == {i} {{ return {i} }}\n" for i in range(12)) + "  return 0\n}\n"),
        (Language.OBJECTIVE_C, "@implementation A\n- (int)f:(int)x {\n" + "".join(f"  if (x == {i}) {{ return {i}; }}\n" for i in range(12)) + "  return 0;\n}\n@end\n"),
    ],
)
def test_real_lizard_other_languages(language, code):
    issues = lizard_runner.run(code, SPECS[language])
    assert [issue.tool for issue in issues] == ["lizard"]


def test_pipeline_routes_objective_c_to_lizard_only():
    code = "@implementation A\n- (int)f:(int)x {\n" + "".join(f"  if (x == {i}) {{ return {i}; }}\n" for i in range(12)) + "  return 0;\n}\n@end\n"
    result = analyze(code, Language.OBJECTIVE_C)
    assert result.language == "objectivec"
    assert {issue.tool for issue in result.issues} == {"lizard"}
    assert result.tool_errors == {}
