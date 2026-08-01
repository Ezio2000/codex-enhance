"""Strict public request and result models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProtocolName = Literal["openai", "anthropic"]
EmbeddingProtocol = Literal["openai"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Usage(StrictModel):
    input_tokens: Annotated[int | None, Field(default=None, ge=0)]
    output_tokens: Annotated[int | None, Field(default=None, ge=0)]
    total_tokens: Annotated[int | None, Field(default=None, ge=0)]


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


class ModelResult(StrictModel):
    protocol: ProtocolName
    model: str
    text: str
    finish_reason: str | None = None
    request_id: str | None = None
    usage: Usage = Field(default_factory=Usage)
    warnings: list[str] = Field(default_factory=list)


class ModelsResult(StrictModel):
    protocol: ProtocolName
    vendor: Literal["generic", "minimax"]
    models: list[str]


class EmbedArtifactResult(StrictModel):
    artifact_path: str
    protocol: EmbeddingProtocol
    model: str
    dimension: Annotated[int, Field(ge=1)]
    count: Annotated[int, Field(ge=1)]
    request_ids: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    warnings: list[str] = Field(default_factory=list)
