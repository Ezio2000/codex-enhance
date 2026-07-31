from __future__ import annotations

from code_enhance_mcp.chunking import chunk_text
from code_enhance_mcp.constants import MAX_CHARS, MAX_LINES, OVERLAP_LINES


def test_chunking_is_deterministic_bounded_and_overlapping() -> None:
    text = "".join(
        f"line {number} {'x' * 45}\n" if number % 25 else "\n"
        for number in range(1, 401)
    )

    first = chunk_text(text)
    second = chunk_text(text)

    assert first == second
    assert len(first) > 2
    assert all(len(chunk.text) <= MAX_CHARS for chunk in first)
    assert all(chunk.end_line - chunk.start_line + 1 <= MAX_LINES for chunk in first)
    for left, right in zip(first, first[1:], strict=False):
        assert left.end_line - right.start_line + 1 == OVERLAP_LINES


def test_empty_or_whitespace_text_produces_no_content_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("\n\n") == []


def test_single_long_line_respects_hard_character_limit() -> None:
    chunks = chunk_text("x" * (MAX_CHARS * 2 + 17))

    assert [len(chunk.text) for chunk in chunks] == [MAX_CHARS, MAX_CHARS, 17]
    assert all(chunk.start_line == 1 and chunk.end_line == 1 for chunk in chunks)
