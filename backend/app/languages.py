"""Supported languages and which analyzers run for each.

This table is the single place that decides what runs where. Adding a language means adding
one entry here (plus Semgrep rules in backend/rules/ if it uses Semgrep).

Data only, no analyzer imports: schemas.py imports Language from here, and analyzers import
schemas, so importing analyzers here would create a cycle. The pipeline maps the analyzer
names below to modules.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    C = "c"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    OBJECTIVE_C = "objectivec"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    YAML = "yaml"
    JSON = "json"


@dataclass(frozen=True)
class LanguageSpec:
    language: Language
    label: str
    extensions: tuple[str, ...]  # first one is used for the temp file
    comment_prefixes: tuple[str, ...]  # line comments, for the lines-of-code count
    analyzers: tuple[str, ...]  # analyzer names, resolved in pipeline.py

    @property
    def temp_ext(self) -> str:
        # Semgrep and Lizard detect the language from the file extension.
        return self.extensions[0]


# Shared analyzer sets.
PYTHON_TOOLS = ("pylint", "bandit", "radon")
CODE_TOOLS = ("semgrep", "lizard")  # languages with functions that Semgrep can parse

C_STYLE = ("//",)
HASH = ("#",)

SPECS: dict[Language, LanguageSpec] = {
    spec.language: spec
    for spec in [
        LanguageSpec(Language.PYTHON, "Python", (".py", ".pyw"), HASH, PYTHON_TOOLS),
        LanguageSpec(Language.JAVASCRIPT, "JavaScript", (".js", ".jsx", ".mjs", ".cjs"), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.TYPESCRIPT, "TypeScript", (".ts", ".tsx", ".mts", ".cts"), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.JAVA, "Java", (".java",), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.CSHARP, "C#", (".cs",), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.GO, "Go", (".go",), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.RUST, "Rust", (".rs",), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.CPP, "C++", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"), C_STYLE, CODE_TOOLS),
        # .h is ambiguous (C, C++, Objective-C); C is the safest default.
        LanguageSpec(Language.C, "C", (".c", ".h"), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.PHP, "PHP", (".php",), ("//", "#"), CODE_TOOLS),
        LanguageSpec(Language.RUBY, "Ruby", (".rb",), HASH, CODE_TOOLS),
        LanguageSpec(Language.SWIFT, "Swift", (".swift",), C_STYLE, CODE_TOOLS),
        LanguageSpec(Language.KOTLIN, "Kotlin", (".kt", ".kts"), C_STYLE, CODE_TOOLS),
        # Semgrep can't parse Objective-C, so only complexity is static; the AI covers the rest.
        LanguageSpec(Language.OBJECTIVE_C, "Objective-C", (".m", ".mm"), C_STYLE, ("lizard",)),
        LanguageSpec(Language.SQL, "SQL", (".sql",), ("--",), ("sqlfluff",)),
        LanguageSpec(Language.HTML, "HTML", (".html", ".htm"), (), ("semgrep",)),
        LanguageSpec(Language.CSS, "CSS", (".css",), (), ("css",)),
        LanguageSpec(Language.YAML, "YAML", (".yaml", ".yml"), HASH, ("yaml", "semgrep")),
        LanguageSpec(Language.JSON, "JSON", (".json",), (), ("json", "semgrep")),
    ]
}

_BY_EXTENSION = {ext: spec.language for spec in SPECS.values() for ext in spec.extensions}


def detect_language(filename: str) -> Language | None:
    """Map a filename to a language by extension (case-insensitive), or None if unknown."""
    return _BY_EXTENSION.get(PurePath(filename).suffix.lower())
