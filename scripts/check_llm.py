"""End-to-end check that the configured LLM provider works. Calls the REAL API and uses quota,
so it is a manual script and never part of pytest.

Usage, from the repo root (settings come from .env, see .env.example):
    backend/.venv/Scripts/python scripts/check_llm.py
    backend/.venv/Scripts/python scripts/check_llm.py --file path/to/code.go --language go

With no --file it reviews a small snippet with a known logic bug: process() returns `result`,
which is unbound when int() raises. Pylint misses it; the AI review should catch it.

Result: PASS (exit 0), WARN (exit 0: it worked, but the known bug wasn't found or one chunk
failed), FAIL (exit 1: misconfigured, or no usable AI review).
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402  (imports after the sys.path line on purpose)

from app.languages import Language  # noqa: E402
from app.llm.client import LLMClient  # noqa: E402
from app.llm.config import LLMConfigError, load_settings  # noqa: E402
from app.pipeline import analyze  # noqa: E402

SNIPPET = '''\
def process(data):
    try:
        result = int(data) * 2
    except ValueError:
        print("invalid input")
    return result


def add_item(item, items=[]):
    items.append(item)
    return items
'''
PROCESS_LINES = range(1, 7)  # where the unbound-`result` bug lives in SNIPPET


class CountingTransport(httpx.HTTPTransport):
    """Counts HTTP requests, so we can see how many attempts the retries needed."""

    def __init__(self):
        super().__init__()
        self.requests = 0

    def handle_request(self, request):
        self.requests += 1
        return super().handle_request(request)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", type=Path, help="review this file instead of the built-in snippet")
    parser.add_argument("--language", default="python", choices=[language.value for language in Language])
    args = parser.parse_args()

    try:
        settings = load_settings()
    except LLMConfigError as exc:
        print(f"FAIL: bad LLM settings in .env: {exc}")
        return 1
    if settings is None:
        print("FAIL: LLM_PROVIDER is off. Set it in .env (see .env.example).")
        return 1
    # Never print the key itself.
    print(f"provider: {settings.provider}   model: {settings.model}   key: {'set' if settings.api_key else 'none'}")

    code = args.file.read_text(encoding="utf-8") if args.file else SNIPPET
    transport = CountingTransport()
    started = time.monotonic()
    result = analyze(code, Language(args.language), LLMClient(settings, transport=transport))
    elapsed = time.monotonic() - started

    review = result.ai_review
    print(f"lines: {len(code.splitlines())}   chunks: {review.chunks}{' (truncated)' if review.truncated else ''}   "
          f"HTTP requests: {transport.requests}   time: {elapsed:.1f}s")
    print(f"confirmed: {review.confirmed}   false positives: {review.false_positives}   "
          f"new: {review.added}   overridden: {review.overridden}")
    for issue in result.issues:
        verdict = issue.ai.verdict.value if issue.ai else "-"
        print(f"  L{issue.line:<4} {issue.severity.value:<8} {issue.tool:<7} {verdict:<15} {issue.message[:70]}")

    if review.error and review.chunks == 0:
        print(f"FAIL: {review.error}")
        return 1
    if review.error:
        print(f"WARN: partial review: {review.error}")
        return 0
    if not args.file:
        caught = any(issue.tool == "ai" and issue.line in PROCESS_LINES for issue in result.issues)
        if not caught:
            print("WARN: the provider works, but the AI missed the unbound `result` bug in process()")
            return 0
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
