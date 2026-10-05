"""Measure the AI reviewer on the annotated snippets in backend/evals/snippets.

Calls the REAL provider (uses quota), so it is a manual script and never part of pytest.

Usage, from the repo root:
    backend/.venv/Scripts/python scripts/eval_prompt.py --provider groq --label baseline
    backend/.venv/Scripts/python scripts/eval_prompt.py --set heldout --provider groq --label final
    backend/.venv/Scripts/python scripts/eval_prompt.py --rescore backend/evals/results/<file>.json

Each run is saved to backend/evals/results/ with the provider, model, a hash of the system
prompt and every response, so results can be compared across prompt versions and re-scored
(--rescore) after a harness change without calling the API again.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.llm.client import LLMClient  # noqa: E402  (imports after the sys.path line on purpose)
from app.llm.config import LLMConfigError, load_settings  # noqa: E402
from app.llm.prompt import SYSTEM_PROMPT  # noqa: E402
from app.pipeline import analyze  # noqa: E402
from app.schemas import AnalyzeResponse  # noqa: E402
from evals.harness import as_dict, load_snippets, score, totals  # noqa: E402

RESULTS_DIR = BACKEND / "evals" / "results"
PAUSE_SECONDS = 2  # between snippets, to stay well under free-tier requests per minute
ERROR_PAUSE_SECONDS = 30  # before re-running a snippet whose AI review failed (e.g. a 503 spell)


def prompt_hash() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8]


def print_report(scores, summary: dict, meta: dict) -> None:
    print(f"\n{meta['provider']} / {meta['model']}   prompt {meta['prompt']}   set: {meta['set']}")
    for s in scores:
        flags = []
        if s.missed:
            flags.append(f"missed {', '.join(s.missed)}")
        if s.extras:
            flags.append(f"{len(s.extras)} extra: {'; '.join(s.extras)}")
        if s.fp_total:
            flags.append(f"planted FP dismissed {s.fp_correct}/{s.fp_total}")
        flags += [f"wrong dismissal: {d}" for d in s.wrong_dismissals]
        flags += s.fix_violations
        if s.clean_violation:
            flags.append("clean file got AI issues")
        if s.error:
            flags.append(f"ERROR {s.error}")
        seconds = f"{s.seconds:5.1f}s" if s.seconds is not None else "   -  "
        print(f"  {s.split:8} {s.name:36} {s.found}/{s.expected}  {seconds}  {' | '.join(flags)}")
    print("totals: " + "   ".join(f"{key}={value}" for key, value in summary.items()))


def run(args) -> int:
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider  # wins over .env (load_dotenv override=False)
        # Switching provider here must not fall back to LLM_API_KEY, which holds the key for
        # whatever provider .env is set up for: that would send it to the wrong company.
        load_dotenv(BACKEND.parent / ".env", override=False)
        own_key = f"{args.provider.upper()}_API_KEY"
        if args.provider != "ollama" and not os.getenv(own_key, "").strip():
            print(f"--provider {args.provider} needs {own_key} in .env (LLM_API_KEY is not used here)")
            return 1
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    try:
        settings = load_settings()
    except LLMConfigError as exc:
        print(f"bad LLM settings: {exc}")
        return 1
    if settings is None:
        print("LLM_PROVIDER is off; pass --provider or set it in .env")
        return 1

    client = LLMClient(settings)
    snippets = load_snippets(args.set)
    scores, records = [], []
    for n, snippet in enumerate(snippets):
        if n:
            time.sleep(PAUSE_SECONDS)
        started = time.monotonic()
        response = analyze(snippet.code, snippet.language, client)
        if response.ai_review.error and "rate limited" not in response.ai_review.error:
            # A 503 spell would score as "the prompt missed everything" and skew the comparison,
            # so try once more after a pause. Rate limits are not retried: that only burns quota.
            print(f"  {snippet.name}: {response.ai_review.error[:80]}; retrying in {ERROR_PAUSE_SECONDS}s", flush=True)
            time.sleep(ERROR_PAUSE_SECONDS)
            started = time.monotonic()
            response = analyze(snippet.code, snippet.language, client)
        seconds = round(time.monotonic() - started, 1)
        scores.append(score(snippet, response, seconds))
        records.append({"name": snippet.name, "seconds": seconds, "response": response.model_dump(mode="json")})
        print(f"  {snippet.name}: {seconds}s", flush=True)

    meta = {"date": date.today().isoformat(), "provider": settings.provider, "model": settings.model,
            "label": args.label, "set": args.set, "prompt": prompt_hash()}
    summary = totals(scores)
    print_report(scores, summary, meta)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{meta['date']}-{settings.provider}-{args.label}-{args.set}.json"
    path.write_text(json.dumps({"meta": meta, "totals": summary, "scores": [as_dict(s) for s in scores],
                                "responses": records}, indent=2), encoding="utf-8")
    print(f"saved {path.relative_to(BACKEND.parent)}")
    return 0


def rescore(path: Path) -> int:
    saved = json.loads(path.read_text(encoding="utf-8"))
    by_name = {snippet.name: snippet for snippet in load_snippets("all")}
    scores = [
        score(by_name[record["name"]], AnalyzeResponse.model_validate(record["response"]), record["seconds"])
        for record in saved["responses"]
    ]
    print_report(scores, totals(scores), saved["meta"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the AI reviewer on annotated snippets.")
    parser.add_argument("--set", default="tuning", choices=["tuning", "heldout", "all"])
    parser.add_argument("--provider", choices=["gemini", "groq", "ollama"], help="overrides LLM_PROVIDER")
    parser.add_argument("--model", help="overrides LLM_MODEL")
    parser.add_argument("--label", default="run", help="name for the results file, e.g. baseline")
    parser.add_argument("--rescore", type=Path, help="re-score a saved results file; no API calls")
    args = parser.parse_args()
    return rescore(args.rescore) if args.rescore else run(args)


if __name__ == "__main__":
    sys.exit(main())
