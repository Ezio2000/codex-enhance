"""Strict public request and result models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ProtocolName = Literal["openai", "anthropic"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Usage(StrictModel):
    input_tokens: Annotated[int | None, Field(default=None, ge=0)]
    output_tokens: Annotated[int | None, Field(default=None, ge=0)]
    total_tokens: Annotated[int | None, Field(default=None, ge=0)]


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
