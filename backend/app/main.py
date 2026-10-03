import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.pipeline import analyze
from app.schemas import AnalyzeRequest, AnalyzeResponse

app = FastAPI(title="AI Code Review Platform", version="0.1.0")

# The frontend (Vite dev server now, Vercel later) runs on a different origin than the API,
# so the browser needs CORS headers. Origins come from env so deploys don't need code changes.
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_code(request: AnalyzeRequest) -> AnalyzeResponse:
    # Plain `def` (not async): FastAPI runs it in a threadpool, so the blocking analyzer
    # subprocesses we add on Day 2 won't freeze the event loop.
    return analyze(request.code)
