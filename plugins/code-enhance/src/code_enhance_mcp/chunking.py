"""Deterministic line-aware text chunking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .constants import MAX_CHARS, MAX_LINES, OVERLAP_LINES, TARGET_CHARS


@dataclass(frozen=True)
class TextChunk:
    start_line: int
    end_line: int
    text: str
    content_hash: str


def chunk_text(text: str) -> list[TextChunk]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return []
    chunks: list[TextChunk] = []
    start = 0
    while start < len(lines):
        if len(lines[start]) > MAX_CHARS:
            for offset in range(0, len(lines[start]), MAX_CHARS):
                content = lines[start][offset : offset + MAX_CHARS]
                chunks.append(
                    TextChunk(
                        start_line=start + 1,
                        end_line=start + 1,
                        text=content,
                        content_hash=hashlib.sha256(
                            content.encode("utf-8")
                        ).hexdigest(),
                    )
                )
            start += 1
            continue
        char_count = 0
        hard_end = start
        blank_candidates: list[int] = []
        while hard_end < len(lines) and hard_end - start < MAX_LINES:
            next_size = char_count + len(lines[hard_end])
            if hard_end > start and next_size > MAX_CHARS:
                break
            char_count = next_size
            hard_end += 1
            if not lines[hard_end - 1].strip() and char_count >= TARGET_CHARS:
                blank_candidates.append(hard_end)
            if char_count >= TARGET_CHARS and blank_candidates:
                break
        end = blank_candidates[-1] if blank_candidates else hard_end
        if end <= start:
            end = min(start + 1, len(lines))
        content = "".join(lines[start:end])
        if content.strip():
            chunks.append(
                TextChunk(
                    start_line=start + 1,
                    end_line=end,
                    text=content,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )
        if end >= len(lines):
            break
        next_start = max(start + 1, end - OVERLAP_LINES)
        start = next_start
    return chunks
