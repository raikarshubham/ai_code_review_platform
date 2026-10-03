import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.languages import SPECS, Language, detect_language
from app.main import app
from app.schemas import AnalyzeRequest
from app.scoring import count_loc

client = TestClient(app)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("main.py", Language.PYTHON),
        ("App.tsx", Language.TYPESCRIPT),
        ("index.mjs", Language.JAVASCRIPT),
        ("Main.java", Language.JAVA),
        ("Program.cs", Language.CSHARP),
        ("widget.hpp", Language.CPP),
        ("util.h", Language.C),
        ("AppDelegate.m", Language.OBJECTIVE_C),
        ("lib.rs", Language.RUST),
        ("build.gradle.kts", Language.KOTLIN),
        ("schema.SQL", Language.SQL),  # extension match is case-insensitive
        ("docker-compose.yml", Language.YAML),
        ("src/pages/index.HTML", Language.HTML),
    ],
)
def test_detect_language_from_extension(filename, expected):
    assert detect_language(filename) == expected


@pytest.mark.parametrize("filename", ["README", "notes.txt", "archive.tar.gz", ""])
def test_detect_language_unknown(filename):
    assert detect_language(filename) is None


def test_every_language_has_a_spec_with_unique_extensions():
    assert set(SPECS) == set(Language)
    extensions = [ext for spec in SPECS.values() for ext in spec.extensions]
    assert len(extensions) == len(set(extensions))
    assert all(ext.startswith(".") and ext == ext.lower() for ext in extensions)


def test_request_language_resolution():
    assert AnalyzeRequest(code="x").language == Language.PYTHON  # old clients: code only
    assert AnalyzeRequest(code="x", filename="a.go").language == Language.GO
    # An explicit language wins over the filename.
    assert AnalyzeRequest(code="x", filename="a.go", language="rust").language == Language.RUST


def test_request_unknown_extension_without_language_is_rejected():
    with pytest.raises(ValidationError, match="could not detect language"):
        AnalyzeRequest(code="x", filename="notes.txt")


def test_api_rejects_unknown_language_value():
    response = client.post("/analyze", json={"code": "x", "language": "cobol"})
    assert response.status_code == 422


def test_api_rejects_undetectable_filename():
    response = client.post("/analyze", json={"code": "x", "filename": "notes.txt"})
    assert response.status_code == 422
    assert "send the 'language' field" in response.text


def test_api_echoes_language():
    response = client.post("/analyze", json={"code": "def add(a, b):\n    return a + b\n"})
    assert response.json()["language"] == "python"


@pytest.mark.parametrize(
    ("code", "prefixes", "expected"),
    [
        ("// header\nint x = 1;\n\n  // note\nreturn x; // trailing\n", ("//",), 2),
        ("-- comment\nSELECT 1;\n", ("--",), 1),
        ("<p>hi</p>\n\n<p>there</p>\n", (), 2),  # no line comments at all
    ],
)
def test_count_loc_per_language_comments(code, prefixes, expected):
    assert count_loc(code, prefixes) == expected
