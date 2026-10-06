# AI Code Review & Bug Detection Platform

A developer tool that analyzes code in 19 languages (Python first-class) for bugs, security
vulnerabilities, code smells and complexity issues, and gives AI-written explanations and fix
suggestions.
This is a portfolio project for campus placements. I need to understand and explain every
part of it in interviews, so explain non-obvious decisions as you go, and keep code readable
over clever.

## Core design: hybrid, not LLM-only

1. **Static analysis first** (deterministic and reliable). Run the tools as subprocesses on a temp
   file with a timeout, and never execute the submitted code. Which tools run is set per
   language in `backend/app/languages.py`, the one list the backend and frontend both use:
   - Python: Pylint (bugs, smells), Bandit (security), Radon (complexity).
   - JS/TS, Java, C#, Go, Rust, C/C++, PHP, Ruby, Swift, Kotlin: Semgrep with our own rules, plus
     Lizard (complexity). Objective-C: Lizard only. HTML: Semgrep.
   - SQL: SQLFluff plus our own check for UPDATE/DELETE without WHERE. YAML: yamllint + Semgrep.
     JSON: our own parser checks + Semgrep. CSS: our own checks with tinycss2.
2. **Normalize** every tool's output into one `Issue` model:
   `tool, rule_id, category (security|bug|smell|complexity|style), severity
   (critical|high|medium|low|info), line, end_line, message, symbol`.
3. **AI review layer**: send line-numbered code plus static findings to an LLM and get JSON back:
   confirm or reject each finding (false-positive filtering), add logic bugs the tools missed,
   and explain each issue with a fix.
4. **Score** 0-100, with penalties scaled by code size.

## Rules for the AI layer
- Use free LLMs through one OpenAI-compatible client (httpx), configured with `.env`:
  `LLM_PROVIDER=gemini|groq|ollama|off`, `LLM_API_KEY`, optional `LLM_MODEL`.
  Defaults: gemini -> `gemini-3.5-flash-lite` (fastest and most reliable on the free tier, measured on Day 6) at `https://generativelanguage.googleapis.com/v1beta/openai`,
  groq -> `llama-3.3-70b-versatile` at `https://api.groq.com/openai/v1`.
- Validate everything the model returns. Drop unknown finding ids, out-of-range line numbers,
  and style-category issues.
- The model may never dismiss a **critical** security finding as a false positive.
- False positives stay in the response but don't count toward the score.
- Retry once on invalid JSON. Back off on HTTP 429 using Retry-After. If the LLM fails, return
  the static results with an `ai_review.error` message instead of failing the request.
- Tell the model the language, and send line-numbered code in a fence tagged with that language.
- For long files, split into chunks by top-level function/class: `ast` for Python, and the
  function start/end lines from Lizard for the other languages it supports. Fall back to
  fixed-size line windows for languages with no function boundaries (SQL, YAML, JSON, CSS, HTML).
- Don't send info-level findings to the LLM, to save free-tier quota.
- Tests must never call a real LLM. Use `httpx.MockTransport`.

## Stack
- Backend: Python 3.11, FastAPI, Pydantic v2, pytest. Layout: `backend/app/{main,pipeline,schemas,languages}.py`,
  `backend/app/analyzers/`, `backend/app/llm/`, `backend/rules/`, `backend/tests/`, `backend/samples/buggy.py`.
- Semgrep lives in its own venv, `backend/.venv-semgrep`, because its opentelemetry pin conflicts
  with FastAPI's. Never add it to `requirements.txt`. We call `semgrep-core` directly, so the
  version stays pinned exactly in `requirements-semgrep.txt`.
- Semgrep rules: write our own in `backend/rules/`, never copy from the Semgrep Registry (its
  license doesn't allow use in a service). Every rule file needs a fixture with
  `ruleid:`/`ok:` comments, and no rule message may contain `$` (Semgrep substitutes it).
- Frontend: React + Vite, Monaco (bundled via `loader.config`, editor core + basic-language
  highlighters only, no language services), Vitest for pure modules in `src/editor/`.
- History lives in the browser (IndexedDB, via `idb`); there is no server database, on purpose.
- Later: Docker, deploy to Render or Railway (backend) and Vercel (frontend).

## Severity calibration
Bandit's defaults understate real risk. Override them: shell injection, `os.system` and SQL
injection are critical; pickle, yaml.load, eval, exec and hardcoded passwords are high;
md5/sha1 is medium; "imported pickle/subprocess" warnings are info.
Treat these Pylint warnings as high-severity bugs: mutable default argument (W0102) and bare except (W0702).
Our Semgrep rules set category and severity in their `metadata` using the same scale: command and
SQL injection are critical, eval and hardcoded secrets are high.

## Build plan (2-3 hours a day; do one day per session)
- Day 1: repo setup, FastAPI `/health` + `/analyze`, React shell
- Day 2: Pylint + Bandit runners, JSON output parsed
- Day 3: Radon, `Issue` normalization, dedupe, sort, score, tests on `samples/buggy.py`
- Day 3.5 (added): 19-language support: language list, Lizard, Semgrep with our own rules,
  SQL/YAML/JSON/CSS checks, language picker in the frontend
- Day 4: LLM client + reviewer prompt + validation (language-aware)
- Day 5: retries, rate limits, chunking, fallback; `scripts/check_llm.py` end-to-end check
- Day 6: tune the prompt on 10-15 buggy snippets. Key target: catch `process()` in
  samples/buggy.py returning `result`, which is unbound when the try block raises
  (Pylint misses this). Paused for the free-tier quota and finished after Days 8-10:
  prompt v2 waits on branch `day6-prompt-v2` until a measured run shows it helps.
- Day 7: buffer
- Day 8-10: Monaco editor, inline severity annotations, side-by-side fix diffs
- Day 11-12: dashboard (score, issues by category, complexity chart), history. Changed
  2026-10-06: history is stored in the browser (IndexedDB), not in PostgreSQL, for privacy and
  because there are no accounts. Day 11 = history, Day 12 = dashboard.
- Day 13-14: Docker, deploy, README with architecture diagram, demo video

## Working agreements
- Start each day in plan mode, show me the plan, then build.
- Write tests alongside code and run `pytest` before saying a step is done.
- Commit after each working step with a clear message. Never commit `.env`.
- At the end of each day, update the roadmap checkboxes in README.md and tell me
  2-3 things from today I should be able to explain in an interview.
