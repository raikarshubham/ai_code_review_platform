"""API data models.

Every analyzer (Pylint, Bandit, Radon, Semgrep, Lizard, ..., the AI reviewer) gets normalized
into the same `Issue` shape, so the scorer and the frontend only ever deal with one format.
"""

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.languages import Language, detect_language

# Big enough for any realistic single file, small enough that one request can't tie up
# the analyzer subprocesses (or burn LLM quota) for minutes.
MAX_CODE_CHARS = 100_000


class Category(str, Enum):
    # str-based Enum so values serialize to plain strings in JSON ("security", not 0).
    SECURITY = "security"
    BUG = "bug"
    SMELL = "smell"
    COMPLEXITY = "complexity"
    STYLE = "style"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Issue(BaseModel):
    tool: str = Field(description="Which analyzer found it: pylint, bandit, radon, ai, python")
    rule_id: str = Field(description="Tool-specific rule id, e.g. W0102 or B602")
    category: Category
    severity: Severity
    line: int = Field(ge=1)
    end_line: int | None = Field(default=None, ge=1)
    message: str
    symbol: str | None = Field(default=None, description="Human-readable rule name")


class AnalyzeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)
    language: Language | None = None
    filename: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def resolve_language(self) -> "AnalyzeRequest":
        """Explicit language wins, then the filename's extension, then Python.

        Python is the default only when no filename is given, so old clients that send just
        `code` keep working. An unrecognised extension is an error rather than a silent guess.
        """
        if self.language is None:
            if self.filename is None:
                self.language = Language.PYTHON
            else:
                detected = detect_language(self.filename)
                if detected is None:
                    raise ValueError(
                        f"could not detect language from filename {self.filename!r}; "
                        "send the 'language' field"
                    )
                self.language = detected
        return self


class AIReview(BaseModel):
    """Status of the LLM layer. Filled in from Day 4; `error` is set when the LLM fails
    and we fall back to static results instead of failing the whole request."""

    enabled: bool = False
    error: str | None = None


class AnalyzeResponse(BaseModel):
    language: Language
    issues: list[Issue]
    score: int = Field(ge=0, le=100)
    summary: dict[Severity, int] = Field(description="Issue count per severity")
    tool_errors: dict[str, str] = Field(
        default_factory=dict,
        description="Analyzers that failed (tool -> reason). Other tools' results are still returned.",
    )
    ai_review: AIReview = Field(default_factory=AIReview)
