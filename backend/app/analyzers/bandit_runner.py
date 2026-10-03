"""Bandit: security vulnerabilities."""

import json

from app.analyzers.runner import AnalyzerError, run_tool
from app.languages import LanguageSpec
from app.schemas import Category, Issue, Severity

NAME = "bandit"

ARGS = ["-f", "json", "-q"]

DEFAULT_SEVERITY = {"HIGH": Severity.HIGH, "MEDIUM": Severity.MEDIUM, "LOW": Severity.LOW}

# Bandit's defaults understate real risk (e.g. a hardcoded password is LOW, md5 is HIGH),
# so we recalibrate by test id. See CLAUDE.md "Severity calibration".
SEVERITY_OVERRIDES: dict[str, Severity] = {
    # Injection: attacker-controlled input runs as shell/SQL.
    "B602": Severity.CRITICAL,  # subprocess with shell=True
    "B604": Severity.CRITICAL,  # any function call with shell=True
    "B605": Severity.CRITICAL,  # os.system / starting a process with a shell
    "B608": Severity.CRITICAL,  # SQL built with string formatting
    # Code execution / secrets.
    "B301": Severity.HIGH,  # pickle.loads
    "B506": Severity.HIGH,  # yaml.load
    "B307": Severity.HIGH,  # eval
    "B102": Severity.HIGH,  # exec
    "B105": Severity.HIGH,  # hardcoded password string
    "B106": Severity.HIGH,  # hardcoded password as function argument
    "B107": Severity.HIGH,  # hardcoded password as default argument
    # Weak hashing.
    "B303": Severity.MEDIUM,  # md5/sha1
    "B324": Severity.MEDIUM,  # hashlib md5/sha1
    # Merely importing a module isn't a vulnerability.
    "B403": Severity.INFO,  # import pickle
    "B404": Severity.INFO,  # import subprocess
}


def parse(output: str) -> list[Issue]:
    try:
        report = json.loads(output)
        results = report["results"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AnalyzerError(f"bandit returned unexpected output: {exc}") from exc

    issues = []
    for result in results:
        rule_id = result["test_id"]
        severity = SEVERITY_OVERRIDES.get(rule_id) or DEFAULT_SEVERITY.get(
            result["issue_severity"], Severity.LOW
        )
        line_range = result.get("line_range") or [result["line_number"]]
        issues.append(
            Issue(
                tool=NAME,
                rule_id=rule_id,
                category=Category.SECURITY,
                severity=severity,
                line=result["line_number"],
                end_line=max(line_range),
                message=result["issue_text"],
                symbol=result.get("test_name"),
            )
        )
    return issues


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return parse(run_tool("bandit", ARGS, code, spec.temp_ext))
