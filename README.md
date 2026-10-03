# AI Code Review & Bug Detection Platform

Paste Python code and get bugs, security vulnerabilities, code smells and complexity issues,
each with an AI-written explanation and a suggested fix.

## How it works

It's a hybrid design, not an LLM-only one:

1. **Static analysis** (deterministic): Pylint (bugs, smells), Bandit (security) and Radon
   (complexity) run as subprocesses on a temp file. Submitted code is never executed.
2. **Normalization**: every tool's output becomes one `Issue` model
   (`tool, rule_id, category, severity, line, end_line, message, symbol`).
3. **AI review**: an LLM confirms or rejects each finding to filter false positives, adds
   logic bugs the tools miss, and explains fixes. Its output is validated, and if the LLM
   fails the API still returns the static results.
4. **Scoring**: 0-100, with penalties scaled by code size.

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
uvicorn app.main:app --reload     # http://localhost:8000  (docs at /docs)
pytest                            # run tests
```

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
| POST   | `/analyze` | `{"code": "...", "filename": "x.py"}` | `{issues, score, summary, tool_errors, ai_review}` |

The three analyzers run in parallel. If one crashes or times out (20 s), its error goes in
`tool_errors` and the other tools' results are still returned.

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
- [ ] Day 4: LLM client + reviewer prompt + validation
- [ ] Day 5: Retries, rate limits, chunking, fallback; `scripts/check_llm.py`
- [ ] Day 6: Prompt tuning on 10-15 buggy snippets
- [ ] Day 7: Buffer
- [ ] Day 8-10: Monaco editor, inline severity annotations, side-by-side fix diffs
- [ ] Day 11-12: Dashboard (score, issues by category, complexity chart), PostgreSQL history
- [ ] Day 13-14: Docker, deploy, architecture diagram, demo video
