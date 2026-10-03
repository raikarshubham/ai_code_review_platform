import json
import subprocess
from pathlib import Path

import pytest
import yaml

from app.analyzers import semgrep_runner
from app.analyzers.runner import AnalyzerError
from app.languages import SPECS, Language
from app.pipeline import analyze
from app.schemas import Category, Severity

RULES_DIR = semgrep_runner.RULES_DIR
RULE_FILES = sorted(RULES_DIR.glob("*.yml"))
SEMGREP_CLI = next(
    (p for p in (semgrep_runner.BACKEND_DIR / ".venv-semgrep").glob("*/semgrep*") if p.suffix in ("", ".exe")),
    None,
)

needs_semgrep = pytest.mark.skipif(
    semgrep_runner.find_semgrep_core() is None,
    reason="Semgrep not installed: pip install -r requirements-semgrep.txt into backend/.venv-semgrep",
)


def all_rules():
    for path in RULE_FILES:
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]:
            yield path, rule


# --- Rule pack hygiene (no Semgrep needed) ------------------------------------------------


# Rule packs still being written; this set must be empty when multi-language support is done.
PENDING = {
    Language.CSHARP, Language.RUST, Language.C, Language.CPP, Language.PHP, Language.RUBY,
    Language.SWIFT, Language.KOTLIN, Language.HTML, Language.YAML, Language.JSON,
}


def test_every_semgrep_language_has_a_rule_file():
    for language in semgrep_runner.SEMGREP_LANG:
        if "semgrep" in SPECS[language].analyzers and language not in PENDING:
            assert semgrep_runner.rules_path(language).is_file(), f"missing rules for {language.value}"


def test_rule_metadata_uses_our_scale():
    # A typo here would otherwise crash requests at parse time (Category/Severity lookups).
    for path, rule in all_rules():
        metadata = rule.get("metadata", {})
        assert Category(metadata["category"]), f"{path.name}:{rule['id']}"
        assert Severity(metadata["severity"]), f"{path.name}:{rule['id']}"


def test_rule_ids_unique_and_dot_free():
    ids = [rule["id"] for _, rule in all_rules()]
    assert len(ids) == len(set(ids)), "duplicate rule id"
    assert all("." not in rule_id for rule_id in ids)


def test_every_rule_file_has_a_fixture():
    for path in RULE_FILES:
        fixtures = [p for p in RULES_DIR.glob(f"{path.stem}.*") if p.suffix != ".yml"]
        assert fixtures, f"{path.name} has no test fixture"


@needs_semgrep
@pytest.mark.skipif(SEMGREP_CLI is None, reason="semgrep CLI not found in backend/.venv-semgrep")
def test_semgrep_rule_suite():
    """Every `ruleid:` annotation must match and every `ok:` annotation must not."""
    completed = subprocess.run(
        [str(SEMGREP_CLI), "--test", "--metrics=off", str(RULES_DIR)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert "All tests passed" in output, output


# --- Parser (canned semgrep-core JSON) ---------------------------------------------------


def core_output(results=(), errors=()):
    return ".\r\n" + json.dumps({"version": "1.179.0", "results": list(results), "errors": list(errors)})


def core_result(check_id, line, metadata, severity="ERROR"):
    return {
        "check_id": check_id,
        "path": "snippet.js",
        "start": {"line": line, "col": 1},
        "end": {"line": line + 1, "col": 1},
        "extra": {"message": "  msg  ", "metadata": metadata, "severity": severity},
    }


def test_parse_uses_rule_metadata_and_strips_progress_dot():
    output = core_output([core_result("js-sql-injection", 7, {"category": "security", "severity": "critical"})])
    (issue,) = semgrep_runner.parse(output)
    assert (issue.tool, issue.rule_id, issue.category, issue.severity) == (
        "semgrep", "js-sql-injection", "security", "critical",
    )
    assert (issue.line, issue.end_line, issue.message) == (7, 8, "msg")


def test_parse_falls_back_to_semgrep_severity_without_metadata():
    (issue,) = semgrep_runner.parse(core_output([core_result("x", 1, {}, severity="WARNING")]))
    assert (issue.category, issue.severity) == ("bug", "medium")


def test_parse_error_becomes_syntax_issue():
    error = {
        "error_type": ["PartialParsing", []],
        "severity": "warn",
        "message": "`function f( {` was unexpected",
        "location": {"path": "snippet.js", "start": {"line": 3, "col": 1}},
    }
    (issue,) = semgrep_runner.parse(core_output(errors=[error]))
    assert (issue.rule_id, issue.severity, issue.line) == ("syntax-error", "high", 3)


def test_engine_error_raises():
    error = {"error_type": ["Rule parse error"], "severity": "error", "message": "bad rule"}
    with pytest.raises(AnalyzerError):
        semgrep_runner.parse(core_output(errors=[error]))


@pytest.mark.parametrize("bad_output", ["", "Fatal error: exception", "[]"])
def test_parse_garbage_raises(bad_output):
    with pytest.raises(AnalyzerError):
        semgrep_runner.parse(bad_output)


# --- Real engine through the pipeline ------------------------------------------------------

JS_CODE = """const cp = require('child_process');
function run(userInput, db) {
  cp.exec('ls ' + userInput);
  return db.query("SELECT * FROM t WHERE id = " + userInput);
}
"""


@needs_semgrep
def test_pipeline_javascript_findings():
    result = analyze(JS_CODE, Language.JAVASCRIPT)
    assert result.tool_errors == {}
    rule_ids = {issue.rule_id for issue in result.issues}
    assert {"js-command-injection", "js-sql-injection"} <= rule_ids
    assert result.issues[0].severity == "critical"
    assert result.score <= 50


@needs_semgrep
def test_pipeline_typescript_uses_shared_rules():
    result = analyze("const f = (s: string): number => eval(s);\n", Language.TYPESCRIPT)
    assert [issue.rule_id for issue in result.issues] == ["js-eval"]


@needs_semgrep
def test_pipeline_reports_javascript_syntax_error():
    result = analyze("function f( {\n  return 1;\n", Language.JAVASCRIPT)
    assert any(issue.rule_id == "syntax-error" for issue in result.issues)


@needs_semgrep
@pytest.mark.parametrize(
    ("language", "code", "rule_id"),
    [
        (Language.JAVA, 'class A { boolean f(String s) { return s == "x"; } }\n', "java-string-reference-equality"),
        (Language.GO, 'package a\nimport "crypto/md5"\nfunc f(b []byte) { md5.Sum(b) }\n', "go-weak-hash"),
    ],
)
def test_pipeline_other_languages(language, code, rule_id):
    result = analyze(code, language)
    assert result.tool_errors == {}
    assert rule_id in {issue.rule_id for issue in result.issues}


@needs_semgrep
def test_clean_javascript_scores_100():
    result = analyze("export function add(a, b) {\n  return a + b;\n}\n", Language.JAVASCRIPT)
    assert result.issues == []
    assert result.score == 100
