"""Our own SQL checks as a separate analyzer, so they still run if sqlfluff fails."""

from app.analyzers.sql_runner import unbounded_writes
from app.languages import LanguageSpec
from app.schemas import Issue

NAME = "sql"


def run(code: str, spec: LanguageSpec) -> list[Issue]:
    return unbounded_writes(code)
