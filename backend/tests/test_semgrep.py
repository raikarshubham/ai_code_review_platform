import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from app.analyzers import semgrep_runner
from app.analyzers.runner import AnalyzerError, AnalyzerTimeout
from app.languages import SPECS, Language, detect_language
from app.pipeline import analyze
from app.schemas import Category, Severity

RULES_DIR = semgrep_runner.RULES_DIR
RULE_FILES = sorted(RULES_DIR.glob("*.yml"))
FIXTURES = sorted(p for p in RULES_DIR.iterdir() if p.suffix != ".yml")

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
PENDING: set[Language] = set()


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


def test_rule_messages_have_no_dollar_sign():
    # Semgrep treats $X / $1 in a message as a metavariable or regex group and substitutes the
    # matched text, so "placeholders like $1" was shown to users as "placeholders like co".
    for path, rule in all_rules():
        assert "$" not in rule["message"], f"{path.name}:{rule['id']}"


def test_every_rule_file_has_a_fixture():
    for path in RULE_FILES:
        fixtures = [p for p in RULES_DIR.glob(f"{path.stem}.*") if p.suffix != ".yml"]
        assert fixtures, f"{path.name} has no test fixture"


# --- Rule fixtures, checked against the real engine ---------------------------------------
#
# Fixtures use Semgrep's annotation convention: a comment containing `ruleid: <id>` means the
# next code line MUST match that rule, `ok: <id>` means it must NOT. We check these ourselves
# with semgrep-core (the same engine path production uses) instead of `semgrep --test`, whose
# CLI races on ~/.semgrep/settings.yml across threads on Windows and fails intermittently.

ANNOTATION = re.compile(r"\b(ruleid|ok):\s*([\w-]+(?:\s*,\s*[\w-]+)*)")


def fixture_annotations(fixture: Path) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    """Return (must_match, must_not_match): rule id -> line numbers."""
    must, must_not = defaultdict(set), defaultdict(set)
    pending = []
    for number, line in enumerate(fixture.read_text(encoding="utf-8").splitlines(), start=1):
        found = ANNOTATION.search(line)
        if found:
            pending.append(found)
            continue
        for annotation in pending:
            target = must if annotation.group(1) == "ruleid" else must_not
            for rule_id in annotation.group(2).split(","):
                target[rule_id.strip()].add(number)
        pending = []
    return must, must_not


def engine_matches(rule_file: Path, fixture: Path) -> dict[str, set[int]]:
    language = detect_language(fixture.name)
    completed = subprocess.run(
        [semgrep_runner.find_semgrep_core(), "-rules", str(rule_file),
         "-lang", semgrep_runner.SEMGREP_LANG[language], "-json", str(fixture)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    report = json.loads(completed.stdout[completed.stdout.find("{"):])
    # Any engine error means a rule failed to load (and would silently never fire).
    assert report["errors"] == [], [e.get("message", e)[:300] for e in report["errors"]]
    matches = defaultdict(set)
    for result in report["results"]:
        matches[result["check_id"]].add(result["start"]["line"])
    return matches


def rule_file_for(fixture: Path) -> Path:
    return RULES_DIR / f"{fixture.stem}.yml"


@needs_semgrep
@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.name)
def test_rule_fixture(fixture):
    rule_ids = [rule["id"] for rule in yaml.safe_load(rule_file_for(fixture).read_text(encoding="utf-8"))["rules"]]
    must, must_not = fixture_annotations(fixture)
    actual = engine_matches(rule_file_for(fixture), fixture)

    unknown = (set(must) | set(must_not)) - set(rule_ids)
    assert not unknown, f"annotations for rules not in {rule_file_for(fixture).name}: {unknown}"
    for rule_id in rule_ids:
        missed = must[rule_id] - actual[rule_id]
        unexpected = actual[rule_id] - must[rule_id]
        assert not missed, f"{rule_id} should match lines {sorted(missed)}"
        assert not unexpected, f"{rule_id} matched unannotated lines {sorted(unexpected)}"
        assert not (must_not[rule_id] & actual[rule_id]), f"{rule_id} matched an `ok:` line"


def test_every_rule_has_a_positive_test_case():
    tested = set()
    for fixture in FIXTURES:
        tested |= set(fixture_annotations(fixture)[0])
    untested = {rule["id"] for _, rule in all_rules()} - tested
    assert not untested, f"rules with no `ruleid:` fixture line: {sorted(untested)}"


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


# --- Timeout retry (fake run_tool, no Semgrep needed) --------------------------------------


@pytest.fixture
def fake_semgrep(monkeypatch):
    """Replace run_tool with a script of outcomes: an exception to raise or output to return."""
    outcomes, calls = [], []

    def fake_run_tool(*args, **kwargs):
        calls.append(kwargs["timeout"])
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(semgrep_runner, "find_semgrep_core", lambda: "semgrep-core")
    monkeypatch.setattr(semgrep_runner, "run_tool", fake_run_tool)
    return outcomes, calls


def test_timeout_is_retried_once(fake_semgrep):
    outcomes, calls = fake_semgrep
    good = core_output([core_result("js-eval", 1, {"category": "security", "severity": "high"})])
    outcomes += [AnalyzerTimeout("semgrep timed out after 10s"), good]
    (issue,) = semgrep_runner.run("eval(x)\n", SPECS[Language.JAVASCRIPT])
    assert issue.rule_id == "js-eval"
    assert calls == [semgrep_runner.SEMGREP_TIMEOUT_SECONDS] * 2


def test_second_timeout_gives_up(fake_semgrep):
    outcomes, calls = fake_semgrep
    outcomes += [AnalyzerTimeout("timed out"), AnalyzerTimeout("timed out")]
    with pytest.raises(AnalyzerError, match="timed out"):
        semgrep_runner.run("eval(x)\n", SPECS[Language.JAVASCRIPT])
    assert len(calls) == 2


def test_other_errors_are_not_retried(fake_semgrep):
    outcomes, calls = fake_semgrep
    outcomes += [AnalyzerError("semgrep produced no output (exit 2)")]
    with pytest.raises(AnalyzerError, match="no output"):
        semgrep_runner.run("eval(x)\n", SPECS[Language.JAVASCRIPT])
    assert len(calls) == 1


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
