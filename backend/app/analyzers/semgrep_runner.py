"""Semgrep: security and bug patterns for 15 languages, using OUR rules in backend/rules/.

Why our own rules: the Semgrep registry rules are licensed for internal use only and may not
be offered "as a service", which is exactly what a hosted code-review site does.

Why semgrep-core directly: the `semgrep` CLI is a Python wrapper that takes ~6 s to start on
every call; the engine it wraps answers the same query in ~0.5 s. The engine's flags are an
internal interface, so the Semgrep version is pinned in requirements-semgrep.txt.

Severity and category come from each rule's `metadata`, so the calibration from CLAUDE.md
lives next to the pattern it applies to.
"""

import json
import os
import shutil
from pathlib import Path

from app.analyzers.runner import AnalyzerError, AnalyzerTimeout, run_tool
from app.languages import Language, LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "semgrep"

BACKEND_DIR = Path(__file__).resolve().parents[2]
RULES_DIR = BACKEND_DIR / "rules"

# Our language -> semgrep-core's -lang name.
SEMGREP_LANG = {
    Language.JAVASCRIPT: "js",
    Language.TYPESCRIPT: "ts",
    Language.JAVA: "java",
    Language.CSHARP: "csharp",
    Language.GO: "go",
    Language.RUST: "rust",
    Language.CPP: "cpp",
    Language.C: "c",
    Language.PHP: "php",
    Language.RUBY: "ruby",
    Language.SWIFT: "swift",
    Language.KOTLIN: "kotlin",
    Language.HTML: "html",
    Language.YAML: "yaml",
    Language.JSON: "json",
}

# Languages that share a rule file (the rules list both languages).
RULE_FILE = {Language.TYPESCRIPT: "javascript", Language.CPP: "c"}

# A normal semgrep-core run takes ~0.5 s, but on Windows it has (rarely, not reproducibly) hung
# until killed, and a re-run then finished at once. So: a short timeout and one retry. The
# worst case is 2 x 10 s, the same 20 s as other tools get, but a one-off hang no longer costs
# the user every Semgrep finding.
SEMGREP_TIMEOUT_SECONDS = 10

# Fallback when a rule has no metadata.severity (all of ours do; this is defensive).
DEFAULT_SEVERITY = {"ERROR": Severity.HIGH, "WARNING": Severity.MEDIUM, "INFO": Severity.LOW}


def rules_path(language: Language) -> Path:
    return RULES_DIR / f"{RULE_FILE.get(language, language.value)}.yml"


def find_semgrep_core() -> str | None:
    """SEMGREP_CORE env var, else the isolated backend/.venv-semgrep, else PATH."""
    if os.getenv("SEMGREP_CORE"):
        return os.environ["SEMGREP_CORE"]
    venv = BACKEND_DIR / ".venv-semgrep"
    for candidate in venv.glob("**/site-packages/semgrep/bin/semgrep-core*"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("semgrep-core")


def _is_parse_error(error: dict) -> bool:
    kind = error.get("error_type", [""])
    kind = kind[0] if isinstance(kind, list) else str(kind)
    return "Pars" in kind or "Syntax" in kind or "Lexical" in kind


def parse(output: str) -> list[Issue]:
    # semgrep-core prints a progress "." line before the JSON document.
    start = output.find("{")
    try:
        report = json.loads(output[start:]) if start >= 0 else None
        results = report["results"]
        errors = report.get("errors", [])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AnalyzerError(f"semgrep returned unexpected output: {exc}") from exc

    issues = []
    for result in results:
        extra = result.get("extra", {})
        metadata = extra.get("metadata", {})
        severity = metadata.get("severity") or DEFAULT_SEVERITY.get(extra.get("severity"), "low")
        issues.append(
            Issue(
                tool=NAME,
                rule_id=result["check_id"],
                category=Category(metadata.get("category", "bug")),
                severity=Severity(severity),
                line=result["start"]["line"],
                end_line=result["end"]["line"],
                message=extra.get("message", "").strip(),
                symbol=result["check_id"],
            )
        )

    for error in errors:
        if _is_parse_error(error):
            # Code that doesn't parse: report it like Python's syntax check does.
            issues.append(
                Issue(
                    tool=NAME,
                    rule_id="syntax-error",
                    category=Category.BUG,
                    severity=Severity.HIGH,
                    line=error.get("location", {}).get("start", {}).get("line", 1),
                    message=f"Syntax error: {error.get('message', '').strip()}",
                    symbol="syntax-error",
                )
            )
        elif error.get("severity") == "error":
            # Anything else at error level (a broken rule, an engine crash) is our problem.
            raise AnalyzerError(f"semgrep error: {error.get('message', error)}")
    return issues


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    core = find_semgrep_core()
    if core is None:
        raise AnalyzerError("semgrep-core not found; install requirements-semgrep.txt into backend/.venv-semgrep")
    args = ["-rules", str(rules_path(spec.language)), "-lang", SEMGREP_LANG[spec.language], "-json"]
    try:
        output = run_tool(NAME, args, code, spec.temp_ext, timeout=SEMGREP_TIMEOUT_SECONDS, executable=[core])
    except AnalyzerTimeout:
        # Only a timeout is retried: a crash or bad output would just fail the same way again.
        output = run_tool(NAME, args, code, spec.temp_ext, timeout=SEMGREP_TIMEOUT_SECONDS, executable=[core])
    return parse(output)
