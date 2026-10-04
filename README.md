# AI Code Review & Bug Detection Platform

Paste code in any of 19 languages and get bugs, security vulnerabilities, code smells and
complexity issues, each with an AI-written explanation and a suggested fix.

## How it works

It's a hybrid design, not an LLM-only one:

1. **Static analysis** (deterministic): each language has its own set of tools (see below).
   They run as subprocesses on a temp file. Submitted code is never executed.
2. **Normalization**: every tool's output becomes one `Issue` model
   (`tool, rule_id, category, severity, line, end_line, message, symbol`).
3. **AI review**: an LLM confirms or rejects each finding to filter false positives, adds
   logic bugs the tools miss, and explains fixes. Its output is validated, and if the LLM
   fails the API still returns the static results.
4. **Scoring**: 0-100, with penalties scaled by code size.

## Supported languages

| Language | Tools |
|---|---|
| Python | Pylint, Bandit, Radon |
| JavaScript, TypeScript, Java, C#, Go, Rust, C, C++, PHP, Ruby, Swift, Kotlin | Semgrep (our rules), Lizard |
| Objective-C | Lizard (complexity only) |
| HTML | Semgrep (our rules) |
| SQL | SQLFluff, plus our own check for `UPDATE`/`DELETE` without `WHERE` |
| YAML | yamllint, Semgrep (our rules) |
| JSON | our own parser checks, Semgrep (our rules) |
| CSS | our own checks with tinycss2 |

The list lives in one place, `backend/app/languages.py`, and the frontend reads it from
`GET /languages`. Lizard measures complexity; Semgrep finds bugs and security issues.

**Why our own Semgrep rules:** the rules in the public Semgrep Registry are licensed for internal
use only and can't be offered as a service, so `backend/rules/` has rules written for this
project. Every rule file has a fixture next to it (for example `go.yml` + `go.go`) whose
`ruleid:` / `ok:` comments say which lines must and must not match, and pytest checks them.

## Stack

- **Backend:** Python 3.11+ (developed on 3.13), FastAPI, Pydantic v2, pytest
- **Frontend:** React + Vite
- **Planned:** Monaco editor, PostgreSQL history, Docker, Render/Railway + Vercel

## Running locally

### Backend

```bash
cd backend
py -3.13 -m venv .venv            # or: python3 -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app              # http://localhost:8000  (docs at /docs)
pytest                            # run tests
```

On Windows, `--reload` can leave worker processes behind that keep port 8000 busy, so it's left
off above.

### Semgrep (needed for every language except Python, SQL, CSS and Objective-C)

Semgrep goes in its **own** virtualenv, `backend/.venv-semgrep`:

```bash
cd backend
py -3.13 -m venv .venv-semgrep
.venv-semgrep/Scripts/pip install -r requirements-semgrep.txt
```

Two reasons. Semgrep pins `opentelemetry-api~=1.37`, and FastAPI needs `>=1.44`, so they
can't share a venv. We only ever run it as a subprocess anyway. The backend calls the
`semgrep-core` engine directly, which takes about 0.5 s against about 6 s for the `semgrep` CLI.
Those engine flags are internal, so the version is pinned exactly. The backend finds it in
`.venv-semgrep` automatically (or set `SEMGREP_CORE` to its path). If it's missing, Semgrep
languages report it in `tool_errors` and the Semgrep rule tests are skipped.

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Set `VITE_API_URL` to point the frontend at a different backend. Copy `.env.example` to `.env`
for the backend settings (LLM provider and CORS origins).

## API

| Method | Path       | Body                                  | Returns                                      |
|--------|------------|---------------------------------------|----------------------------------------------|
| GET    | `/health`  | none                                  | `{"status": "ok"}`                           |
| GET    | `/languages` | none                                | `[{id, label, extensions}]`                  |
| POST   | `/analyze` | `{"code": "...", "language": "go"}`   | `{issues, score, summary, tool_errors, ai_review}` |

`language` is optional. If it's missing, the language comes from `filename`'s extension, and
with neither it defaults to Python. An unknown extension is a 422 error, not a guess.

A language's analyzers run in parallel. If one crashes or times out (20 s), its error goes in
`tool_errors` and the other tools' results are still returned.

## AI review

Set `LLM_PROVIDER` (`gemini`, `groq` or `ollama`) and `LLM_API_KEY` in `.env` to turn it on.
All three providers speak the OpenAI chat-completions API, so one small httpx client
(`backend/app/llm/`) talks to all of them. Bad settings stop the server at startup.

The model gets the code with line numbers, in a fence tagged with the language, plus the static
findings as `F1, F2, ...` (info-level ones are left out to save free-tier quota). It replies in
JSON mode with a verdict, explanation and fix for each finding, and any bugs the tools missed.

The reply is treated as untrusted input and validated before it's used:

- verdicts for finding ids we never sent are dropped
- new issues with line numbers outside the file, style issues, or unknown categories and
  severities are dropped
- a **critical security finding can never be dismissed** as a false positive (counted in
  `ai_review.overridden`)
- issues the AI adds are capped at **high**, so only the deterministic tools can mark something
  critical (which caps the score at 50)
- new issues that repeat a static finding on the same line are dropped, and at most 15 are kept
- one malformed item is skipped; only a reply with the wrong overall shape counts as a failure

In the response, each issue can carry an `ai` object:
`{verdict: "confirmed" | "false_positive", explanation, fix, fixed_code, fix_start_line, fix_end_line}`.
`fixed_code` replaces lines `fix_start_line..fix_end_line`. Issues the AI found have
`tool: "ai"`. **False positives stay in the list**, so you can see what was dismissed and why,
but they sort last and don't count toward `score` or `summary`.

If the LLM fails (network error, bad key, unusable reply), `/analyze` still returns the static
results, with the reason in `ai_review.error`. Tests never call a real LLM: they use
`httpx.MockTransport`, and `tests/conftest.py` forces `LLM_PROVIDER=off`.

## Scoring

```
weights = critical 25, high 10, medium 4, low 1, info 0
size    = max(1, sqrt(lines_of_code / 50))
score   = clamp(100 - sum(weights) / size, 0, 100)
any critical issue caps the score at 50
```

Bigger files get a gentler penalty, but less than linearly. The critical cap means one SQL
injection can't be diluted by a large file. Before scoring, findings that several tools
report (for example `eval` from both Pylint and Bandit) are merged into one.

## Roadmap

- [x] Day 1: Repo setup, FastAPI `/health` + `/analyze`, React shell
- [x] Day 2: Pylint + Bandit runners, JSON output parsed
- [x] Day 3: Radon, `Issue` normalization, dedupe, sort, score, tests on `samples/buggy.py`
- [x] Day 3.5: 19 languages: language list, Lizard, Semgrep with our own rules, SQL/YAML/JSON/CSS checks, language picker
- [ ] Day 4: LLM client + reviewer prompt + validation
- [ ] Day 5: Retries, rate limits, chunking, fallback; `scripts/check_llm.py`
- [ ] Day 6: Prompt tuning on 10-15 buggy snippets
- [ ] Day 7: Buffer
- [ ] Day 8-10: Monaco editor, inline severity annotations, side-by-side fix diffs
- [ ] Day 11-12: Dashboard (score, issues by category, complexity chart), PostgreSQL history
- [ ] Day 13-14: Docker, deploy, architecture diagram, demo video
