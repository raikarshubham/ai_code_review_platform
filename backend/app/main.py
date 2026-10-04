import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.languages import SPECS
from app.llm.client import LLMClient
from app.llm.config import load_settings
from app.pipeline import analyze
from app.schemas import AnalyzeRequest, AnalyzeResponse

# Read LLM settings first: this also loads the repo .env, so CORS_ORIGINS below can come from
# it too. Bad settings raise here, so a typo in .env stops startup instead of every request.
_llm_settings = load_settings()
llm_client = LLMClient(_llm_settings) if _llm_settings else None

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


@app.get("/languages")
def languages() -> list[dict]:
    # Served from the registry so the frontend never keeps its own copy of the list.
    return [
        {"id": spec.language.value, "label": spec.label, "extensions": list(spec.extensions)}
        for spec in SPECS.values()
    ]


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_code(request: AnalyzeRequest) -> AnalyzeResponse:
    # Plain `def` (not async): FastAPI runs it in a threadpool, so the blocking analyzer
    # subprocesses don't freeze the event loop.
    return analyze(request.code, request.language, llm_client)
