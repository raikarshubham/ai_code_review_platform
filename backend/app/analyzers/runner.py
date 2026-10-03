"""Shared helper for running an analyzer CLI on submitted code.

Safety: the code is only written to a file and read by tools that parse it into an AST
(Pylint, Bandit, Radon). It is never imported or executed.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 20

# Fixed name: the user's `filename` is never used as a path, so it can't escape the temp dir.
SNIPPET_NAME = "snippet.py"


class AnalyzerError(Exception):
    """The tool crashed, timed out, or produced output we couldn't parse."""


def run_tool(module: str, args: list[str], code: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Write `code` to a temp file, run `python -m <module> <args> snippet.py`, return stdout.

    We don't check the exit code: Pylint and Bandit exit non-zero whenever they *find issues*,
    which is the normal case for us. Callers detect real failures by failing to parse stdout.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        Path(tmp_dir, SNIPPET_NAME).write_text(code, encoding="utf-8")
        # sys.executable -m: always use the tool installed in *this* venv, not one from PATH.
        command = [sys.executable, "-m", module, *args, SNIPPET_NAME]
        try:
            completed = subprocess.run(
                command,
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AnalyzerError(f"{module} timed out after {timeout}s") from exc
        except OSError as exc:
            raise AnalyzerError(f"could not start {module}: {exc}") from exc

    if not completed.stdout.strip():
        stderr_tail = completed.stderr.strip()[-300:]
        raise AnalyzerError(f"{module} produced no output (exit {completed.returncode}): {stderr_tail}")
    return completed.stdout
