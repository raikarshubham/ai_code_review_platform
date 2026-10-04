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


class Verdict(str, Enum):
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"


class AINote(BaseModel):
    """What the LLM said about one issue. Kept separate from the static fields so it's always
    clear which parts came from a deterministic tool and which from the model."""

    verdict: Verdict
    explanation: str
    fix: str | None = None
    fixed_code: str | None = Field(default=None, description="Replaces lines fix_start_line..fix_end_line")
    fix_start_line: int | None = Field(default=None, ge=1)
    fix_end_line: int | None = Field(default=None, ge=1)


class Issue(BaseModel):
    tool: str = Field(description="Which analyzer found it: pylint, bandit, radon, ai, python")
    rule_id: str = Field(description="Tool-specific rule id, e.g. W0102 or B602")
    category: Category
    severity: Severity
    line: int = Field(ge=1)
    end_line: int | None = Field(default=None, ge=1)
    message: str
    symbol: str | None = Field(default=None, description="Human-readable rule name")
    ai: AINote | None = Field(default=None, description="Set when the AI review ran and commented on it")

    @property
    def is_false_positive(self) -> bool:
        return self.ai is not None and self.ai.verdict == Verdict.FALSE_POSITIVE


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
    """Status of the LLM layer. `error` is set when the LLM fails and we fall back to the
    static results instead of failing the whole request."""

    enabled: bool = False
    provider: str | None = None
    model: str | None = None
    confirmed: int = 0
    false_positives: int = 0
    added: int = Field(default=0, description="New issues the AI found that the tools missed")
    overridden: int = Field(default=0, description="Dismissals of critical security findings we refused")
    chunks: int = Field(default=0, description="LLM requests sent; long files are split by function")
    truncated: bool = Field(default=False, description="File too long: only its first chunks were reviewed")
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
