"""Split a long file into chunks for the AI reviewer, cutting only between functions/classes.

Why chunk: free tiers limit tokens per request and per minute, and models review a focused
300 lines better than a 2,000-line wall. Why cut at function boundaries: a chunk that ends in
the middle of a function would make the model guess at code it can't see.

    units    = top-level functions/classes (Python: ast; others: Lizard's function ranges)
    segments = each unit plus the lines before it (imports, module code), covering the file
    chunks   = consecutive segments packed up to MAX_CHUNK_LINES; an oversized segment is
               cut into fixed windows, and files with no units are windows from the start
"""

import ast
from dataclasses import dataclass

from app.analyzers import lizard_runner
from app.analyzers.runner import AnalyzerError
from app.languages import Language, LanguageSpec

MAX_CHUNK_LINES = 300
MAX_CHUNKS = 8  # ~2,400 lines; keeps one review within free-tier requests per minute
HEADER_MAX_LINES = 30


@dataclass(frozen=True)
class Chunk:
    start: int  # 1-based, inclusive
    end: int

    def __contains__(self, line: int) -> bool:
        return self.start <= line <= self.end


@dataclass(frozen=True)
class ChunkPlan:
    chunks: list[Chunk]
    # Lines before the first function (imports, package line). Sent with every chunk after the
    # first as read-only context, so the model doesn't call every imported name undefined.
    header: Chunk | None
    truncated: bool  # the file needed more than MAX_CHUNKS chunks; only the first ones are sent


def plan(code: str, spec: LanguageSpec) -> ChunkPlan:
    line_count = max(1, len(code.splitlines()))
    if line_count <= MAX_CHUNK_LINES:
        # The common case: one chunk, and no need to run Lizard to find functions.
        return ChunkPlan([Chunk(1, line_count)], header=None, truncated=False)

    units = _outermost(_units(code, spec))
    chunks = _pack(_segments(units, line_count))
    header = None
    if units and units[0][0] > 1:
        header = Chunk(1, min(units[0][0] - 1, HEADER_MAX_LINES))
    return ChunkPlan(chunks[:MAX_CHUNKS], header=header, truncated=len(chunks) > MAX_CHUNKS)


def _units(code: str, spec: LanguageSpec) -> list[tuple[int, int]]:
    """Line ranges of top-level functions/classes, or [] if we can't tell (-> plain windows)."""
    if spec.language == Language.PYTHON:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        units = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Decorators sit above the `def` line and belong with their function.
                start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
                units.append((start, node.end_lineno))
        return units
    if "lizard" in spec.analyzers:
        try:
            return lizard_runner.function_ranges(code, spec)
        except AnalyzerError:
            return []  # chunking still works, just without function boundaries
    return []  # SQL, YAML, JSON, CSS, HTML: no functions to cut between


def _outermost(units: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Drop ranges nested inside another (Lizard reports methods and inner functions too)."""
    kept: list[tuple[int, int]] = []
    for start, end in sorted(units, key=lambda unit: (unit[0], -unit[1])):
        if not kept or start > kept[-1][1]:
            kept.append((start, end))
    return kept


def _segments(units: list[tuple[int, int]], line_count: int) -> list[Chunk]:
    """Cover lines 1..line_count: each unit takes the lines before it, the last takes the rest."""
    if not units:
        return [Chunk(1, line_count)]
    segments, start = [], 1
    for _, end in units:
        segments.append(Chunk(start, min(end, line_count)))
        start = min(end, line_count) + 1
    if start <= line_count:
        last = segments.pop()
        segments.append(Chunk(last.start, line_count))
    return segments


def _pack(segments: list[Chunk]) -> list[Chunk]:
    pieces = []
    for segment in segments:
        # A unit longer than a whole chunk can't stay in one piece: cut it into windows.
        for start in range(segment.start, segment.end + 1, MAX_CHUNK_LINES):
            pieces.append(Chunk(start, min(start + MAX_CHUNK_LINES - 1, segment.end)))
    chunks = [pieces[0]]
    for piece in pieces[1:]:
        if piece.end - chunks[-1].start + 1 <= MAX_CHUNK_LINES:
            chunks[-1] = Chunk(chunks[-1].start, piece.end)
        else:
            chunks.append(piece)
    return chunks
