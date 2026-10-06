"""Per-function complexity for the dashboard chart.

The complexity analyzers only turn functions above the threshold into issues, so clean code has
no data to chart. This runs the same tool (Radon for Python, Lizard elsewhere) and keeps every
function, parsed by the same code the issues use, so the chart and the issue text always agree.

Trade-off: the tool runs a second time (~0.3 s), in parallel with the other analyzers, so the
response barely slows down. The alternative was changing the run() -> list[Issue] contract every
analyzer shares; keeping that contract simple seemed worth one extra subprocess.
"""

import logging

from app.analyzers import lizard_runner, radon_runner
from app.analyzers.runner import AnalyzerError
from app.languages import LanguageSpec
from app.schemas import FunctionMetric

logger = logging.getLogger(__name__)


def function_metrics(code: str, spec: LanguageSpec) -> list[FunctionMetric]:
    """Complexity of every function, or [] for languages without functions (SQL, YAML, JSON, CSS,
    HTML) and when the tool fails. A chart is a bonus: it never fails the request or shows up in
    tool_errors (the analyzer itself already reports a real tool failure there)."""
    if "radon" in spec.analyzers:
        runner = radon_runner
    elif "lizard" in spec.analyzers:
        runner = lizard_runner
    else:
        return []
    try:
        return runner.functions(runner.run_raw(code, spec))
    except AnalyzerError as exc:
        logger.warning("function metrics unavailable: %s", exc)
        return []
