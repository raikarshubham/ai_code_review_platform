"""Shared helper for running an analyzer CLI on submitted code.

Safety: the code is only written to a file and read by tools that parse it (Pylint, Bandit,
Radon, Semgrep, Lizard, ...). It is never imported, compiled or executed.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 20

# Fixed stem + an extension from our language table: the user's `filename` is never used as a
# path, so it can't escape the temp dir.
SNIPPET_STEM = "snippet"


class AnalyzerError(Exception):
    """The tool crashed, timed out, or produced output we couldn't parse."""


def run_tool(
    module: str,
    args: list[str],
    code: str,
    temp_ext: str = ".py",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    allow_empty: bool = False,
    executable: list[str] | None = None,
) -> str:
    """Write `code` to snippet<temp_ext>, run the tool on it, return stdout.

    By default runs `python -m <module>` from this venv. `executable` overrides that for tools
    installed elsewhere (Semgrep lives in its own venv because of a dependency conflict).
    `temp_ext` matters because tools like Semgrep and Lizard pick the language from it.

    We don't check the exit code: Pylint and Bandit exit non-zero whenever they *find issues*,
    which is the normal case for us. Callers detect real failures by failing to parse stdout.
    `allow_empty` is for tools that print nothing when there's nothing to report (Lizard on a
    file with no functions); then empty output is only accepted with exit code 0.
    """
    # sys.executable -m: always use the tool installed in *this* venv, not one from PATH.
    base_command = executable or [sys.executable, "-m", module]
    with tempfile.TemporaryDirectory() as tmp_dir:
        snippet_name = SNIPPET_STEM + temp_ext
        # newline="": write the code's line endings as-is. Text mode would turn \n into \r\n on
        # Windows, and line-ending checks (yamllint new-lines) would flag code that is fine.
        Path(tmp_dir, snippet_name).write_text(code, encoding="utf-8", newline="")
        command = [*base_command, *args, snippet_name]
        try:
            completed = subprocess.run(
                command,
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AnalyzerError(f"{module} timed out after {timeout}s") from exc
        except OSError as exc:
            raise AnalyzerError(f"could not start {module}: {exc}") from exc

    if not completed.stdout.strip():
        if allow_empty and completed.returncode == 0:
            return ""
        stderr_tail = completed.stderr.strip()[-300:]
        raise AnalyzerError(f"{module} produced no output (exit {completed.returncode}): {stderr_tail}")
    return completed.stdout
