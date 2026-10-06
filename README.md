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
- **Frontend:** React + Vite, Monaco editor (bundled), Vitest
- **Planned:** PostgreSQL history, Docker, Render/Railway + Vercel

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
npm test                          # unit tests (Vitest)
```

Set `VITE_API_URL` to point the frontend at a different backend. Copy `.env.example` to `.env`
for the backend settings (LLM provider and CORS origins).

### What the UI does

- **Monaco editor** (the editor from VS Code) with syntax highlighting for all 19 languages.
  It's bundled with the app instead of loaded from a CDN. Only the editor core and the
  highlighters are included, not Monaco's own TypeScript/JSON/CSS language services, because
  their error squiggles would compete with ours. It loads lazily in its own chunk, so the page
  appears before the ~700 kB (gzipped) editor arrives.
- **Inline markers.** Every issue is a squiggle on its first line: critical/high = error,
  medium = warning, low = info, info = hint. Hovering shows the message, the AI explanation and
  the fix. A dot in the gutter shows the worst severity on that line. False positives get no
  marker, since they don't count.
- **Click "Line N"** in the issue list to jump there with the issue's full range selected.
- **Fix diffs.** "Show fix" opens a side-by-side diff of the current code against the code with
  the AI fix applied. **Apply fix** writes it into the editor, and Ctrl+Z undoes it.
- **Out-of-date results.** Line numbers only match the code that was analyzed. After any edit or
  applied fix, a banner says so, and the other fixes stay disabled until you re-analyze. A fix is
  never applied to the wrong lines.

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

### Reliability on free tiers

**Retries** (`backend/app/llm/client.py`). At most 3 attempts, all inside a 120 s deadline:

| Failure | What happens |
|---|---|
| 429 rate limited | wait as long as the server says (`Retry-After` header, or Gemini's `retryDelay` in the body), then retry. A wait over 30 s fails right away. |
| 500 / 502 / 503 / 504, connection error | back off 2 s, then 4 s |
| Reply isn't JSON | retry once |
| 400 / 401 / 403 / 404 | no retry: a bad key or a retired model won't fix itself |
| Timeout | no retry: it already used the full 60 s |

**Long files are split into chunks** (`backend/app/llm/chunking.py`). Files over 300 lines are
cut only between top-level functions and classes, so no chunk starts in the middle of a
function. Python uses `ast`; the other languages use Lizard's function ranges; SQL, YAML, JSON,
CSS and HTML use 300-line windows.

Each chunk is sent with its real file line numbers, only its own findings, and the file's
imports as read-only context. Up to 3 chunks run in parallel. If one fails, the rest still
count and `ai_review.error` says "1 of 3 chunks failed". Files needing more than 8 chunks
(~2,400 lines) get `ai_review.truncated`.

**Check your provider** with a real call (uses quota; not part of `pytest`):

```bash
backend/.venv/Scripts/python scripts/check_llm.py                             # known-bug snippet
backend/.venv/Scripts/python scripts/check_llm.py --file app.go --language go  # any file
```

It prints the model, the number of chunks and HTTP requests (so you can see retries) and the
time taken, then PASS, WARN or FAIL (exit code 1).

Free tiers also have a **daily** request quota. On Gemini's free tier it ran out after about 40
reviews in one day of testing. After that, Gemini answers 429 with a wait of several hours. The
AI review is then skipped with `ai_review.error` "rate limited; retry in 5 h 41 min (daily quota
likely used up)", and the static results still come back. Switching `LLM_PROVIDER` to `groq`
in `.env` gives you a separate quota.

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
- [x] Day 4: LLM client + reviewer prompt + validation
- [x] Day 5: Retries, rate limits, chunking, fallback; `scripts/check_llm.py`
- [ ] Day 6: Prompt tuning on 10-15 buggy snippets (in progress: evaluation set, harness and baseline done; paused for the Gemini free-tier quota)
- [ ] Day 7: Buffer
- [x] Day 8-10: Monaco editor, inline severity annotations, side-by-side fix diffs
- [ ] Day 11-12: Dashboard (score, issues by category, complexity chart), PostgreSQL history
- [ ] Day 13-14: Docker, deploy, architecture diagram, demo video
