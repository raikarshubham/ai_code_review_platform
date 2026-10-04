import ast

from app.analyzers import lizard_runner
from app.languages import SPECS, Language
from app.llm import chunking
from app.llm.chunking import MAX_CHUNK_LINES, MAX_CHUNKS, Chunk, plan


def python_function(name: str, body_lines: int, decorator: bool = False) -> str:
    lines = (["@cache"] if decorator else []) + [f"def {name}():"]
    lines += [f"    x{n} = {n}" for n in range(body_lines)] + ["    return 0", "", ""]
    return "\n".join(lines) + "\n"


def assert_covers_every_line_once(chunks: list[Chunk], line_count: int):
    assert chunks[0].start == 1 and chunks[-1].end == line_count
    for before, after in zip(chunks, chunks[1:]):
        assert after.start == before.end + 1


def assert_no_cut_inside(chunks: list[Chunk], units: list[tuple[int, int]]):
    """The point of chunking by function: no chunk may start in the middle of one."""
    for chunk in chunks[1:]:
        assert not any(start < chunk.start <= end for start, end in units), f"cut inside a unit at {chunk.start}"


def python_units(code: str) -> list[tuple[int, int]]:
    tree = ast.parse(code)
    return [(min([n.lineno] + [d.lineno for d in n.decorator_list]), n.end_lineno) for n in tree.body
            if isinstance(n, ast.FunctionDef)]


def test_small_file_is_one_chunk():
    result = plan("x = 1\n" * 50, SPECS[Language.PYTHON])
    assert (result.chunks, result.header, result.truncated) == ([Chunk(1, 50)], None, False)


def test_long_python_file_splits_only_between_top_level_functions():
    header = "import os\nimport sys\n\n"
    code = header + "".join(python_function(f"f{n}", 40, decorator=n % 2 == 0) for n in range(20))
    line_count = len(code.splitlines())
    result = plan(code, SPECS[Language.PYTHON])

    assert len(result.chunks) > 1
    assert_covers_every_line_once(result.chunks, line_count)
    assert all(chunk.end - chunk.start + 1 <= MAX_CHUNK_LINES for chunk in result.chunks)
    assert_no_cut_inside(result.chunks, python_units(code))  # decorators count as part of the function
    assert result.header == Chunk(1, 3)


def test_module_code_between_functions_goes_with_the_next_function():
    # f0 + f1 fill one chunk; the module code before f2 must travel with f2, not stay behind.
    code = python_function("f0", 140) + python_function("f1", 140) + "CONSTANT = 1\n\n" + python_function("f2", 140)
    result = plan(code, SPECS[Language.PYTHON])
    lines = code.splitlines()
    constant_line, f2_line = lines.index("CONSTANT = 1") + 1, lines.index("def f2():") + 1
    assert any(constant_line in chunk and f2_line in chunk for chunk in result.chunks)
    assert not any(constant_line in chunk and 1 in chunk for chunk in result.chunks)


def test_function_longer_than_a_chunk_is_cut_into_windows():
    code = python_function("huge", MAX_CHUNK_LINES * 2)
    result = plan(code, SPECS[Language.PYTHON])
    assert len(result.chunks) == 3
    assert_covers_every_line_once(result.chunks, len(code.splitlines()))


def test_go_uses_lizard_function_ranges():
    functions = "".join(
        f"func f{n}() int {{\n" + "".join(f"\tx{i} := {i}\n\t_ = x{i}\n" for i in range(30)) + "\treturn 0\n}\n\n"
        for n in range(10)
    )
    code = 'package main\n\nimport "fmt"\n\n' + functions
    result = plan(code, SPECS[Language.GO])
    assert len(result.chunks) > 1
    assert_covers_every_line_once(result.chunks, len(code.splitlines()))
    assert_no_cut_inside(result.chunks, lizard_runner.function_ranges(code, SPECS[Language.GO]))
    assert result.header == Chunk(1, 4)


def test_java_methods_inside_a_class_collapse_to_the_outermost_ranges():
    # Lizard reports methods; nested ranges must not produce overlapping chunks.
    methods = "".join(
        f"    int m{n}() {{\n" + "".join(f"        int x{i} = {i};\n" for i in range(50)) + "        return 0;\n    }\n"
        for n in range(8)
    )
    code = "class A {\n" + methods + "}\n"
    result = plan(code, SPECS[Language.JAVA])
    assert len(result.chunks) > 1
    assert_covers_every_line_once(result.chunks, len(code.splitlines()))


def test_languages_without_functions_get_windows():
    code = "".join(f"key{n}: {n}\n" for n in range(MAX_CHUNK_LINES * 2 + 10))
    result = plan(code, SPECS[Language.YAML])
    assert result.chunks == [Chunk(1, 300), Chunk(301, 600), Chunk(601, 610)]
    assert result.header is None


def test_lizard_failure_falls_back_to_windows(monkeypatch):
    def broken(code, spec):
        raise chunking.AnalyzerError("lizard crashed")

    monkeypatch.setattr(chunking.lizard_runner, "function_ranges", broken)
    result = plan("x := 1\n" * 400, SPECS[Language.GO])
    assert result.chunks == [Chunk(1, 300), Chunk(301, 400)]


def test_very_long_files_are_truncated_to_max_chunks():
    code = "x = 1\n" * (MAX_CHUNK_LINES * (MAX_CHUNKS + 2))
    result = plan(code, SPECS[Language.PYTHON])
    assert len(result.chunks) == MAX_CHUNKS and result.truncated
