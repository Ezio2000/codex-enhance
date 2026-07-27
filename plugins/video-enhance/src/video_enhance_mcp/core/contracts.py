"""Contracts separating the core pipeline from provider implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from .schemas import PreparedMedia

ProfileName = Literal["balanced", "temporal", "ocr"]


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    supported_formats: tuple[str, ...]
    max_upload_bytes: int
    supports_audio: bool
    supports_structured_output: bool
    supports_remote_url: bool
    min_fps: float
    max_fps: float
    detail_levels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedVideo:
    path: Path
    metadata: PreparedMedia
    output_duration_ms: int | None


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    prompt: str
    duration_ms: int | None
    profile: ProfileName


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int = 0
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    content: str
    model: str
    detail: str
    fps: float
    structured: bool
    usage: ProviderUsage
    warnings: list[str] = field(default_factory=list)


class VideoProvider(Protocol):
    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    async def analyze(
        self, media: PreparedVideo, request: ProviderRequest
    ) -> ProviderResponse: ...


ProgressPayload = dict[str, Any]
