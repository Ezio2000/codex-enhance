"""Strict request and result models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmbedInput(StrictModel):
    id: Annotated[str, Field(min_length=1, max_length=200)]
    text: Annotated[str | None, Field(default=None, max_length=100_000)]
    path: Annotated[str | None, Field(default=None, max_length=4096)]

    @model_validator(mode="after")
    def validate_source(self) -> EmbedInput:
        if (self.text is None) == (self.path is None):
            raise ValueError("exactly one of text or path is required")
        if self.text is not None and not self.text.strip():
            raise ValueError("text must contain non-whitespace content")
        return self


class Usage(StrictModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class EmbedArtifactResult(StrictModel):
    artifact_path: str
    model: str
    dimension: int
    count: int
    request_ids: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    warnings: list[str] = Field(default_factory=list)


class IndexSyncResult(StrictModel):
    repository_root: str
    scope_path: str
    index_path: str
    files_seen: int
    files_indexed: int
    files_unchanged: int
    files_removed: int
    files_excluded: int
    chunks_embedded: int
    chunks_total: int
    request_ids: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    exclusions: list[dict[str, str]] = Field(default_factory=list)


class SearchMatch(StrictModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    score: float = Field(ge=-1, le=1)
    preview: str


class IndexSearchResult(StrictModel):
    repository_root: str
    index_path: str
    query: str
    matches: list[SearchMatch]
    stale_matches_skipped: int = 0
    request_id: str | None = None
    usage: Usage = Field(default_factory=Usage)
