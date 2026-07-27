"""Public MCP models and the provider-neutral analysis contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MediaInfo(StrictModel):
    path: str
    size_bytes: Annotated[int, Field(ge=0)]
    duration_ms: Annotated[int | None, Field(default=None, ge=0)]
    width: Annotated[int | None, Field(default=None, ge=1)]
    height: Annotated[int | None, Field(default=None, ge=1)]
    container: str | None = None
    has_audio: bool | None = None


class PreparedMedia(StrictModel):
    source: MediaInfo
    upload_size_bytes: Annotated[int, Field(ge=0)]
    normalized: bool
    normalizer: str
    source_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class TimelineEvent(StrictModel):
    start_ms: Annotated[int, Field(ge=0)]
    end_ms: Annotated[int, Field(gt=0)]
    description: Annotated[str, Field(min_length=1, max_length=500)]
    screen_text: Annotated[
        list[Annotated[str, Field(max_length=120)]], Field(max_length=10)
    ] = Field(default_factory=list)
    confidence: Confidence

    @model_validator(mode="after")
    def validate_range(self) -> TimelineEvent:
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class AnalysisPayload(StrictModel):
    summary: Annotated[str, Field(min_length=1, max_length=2000)]
    answer: Annotated[str, Field(default="", max_length=6000)]
    timeline: Annotated[list[TimelineEvent], Field(max_length=20)] = Field(
        default_factory=list
    )
    observations: Annotated[
        list[Annotated[str, Field(max_length=500)]], Field(max_length=30)
    ] = Field(default_factory=list)
    uncertainties: Annotated[
        list[Annotated[str, Field(max_length=500)]], Field(max_length=20)
    ] = Field(default_factory=list)


class Coverage(StrictModel):
    duration_ms: Annotated[int | None, Field(default=None, ge=0)]
    timestamp_valid: bool
    timeline_end_ms: Annotated[int | None, Field(default=None, ge=0)]


class RouteInfo(StrictModel):
    provider: str
    model: str
    profile: Literal["balanced", "temporal", "ocr"]
    detail: str
    fps: Annotated[float, Field(ge=0.1, le=60.0)]
    structured_output: bool


class UsageInfo(StrictModel):
    input_tokens: Annotated[int | None, Field(default=None, ge=0)]
    output_tokens: Annotated[int | None, Field(default=None, ge=0)]
    total_tokens: Annotated[int | None, Field(default=None, ge=0)]
    latency_ms: Annotated[int, Field(ge=0)]
    finish_reason: str | None = None


class VideoInspectResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    media: MediaInfo
    allowed: bool = True
    normalization_required: bool
    recommended_profile: Literal["balanced"] = "balanced"


class VideoAnalyzeResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["completed", "partial"]
    analysis: AnalysisPayload
    media: PreparedMedia
    coverage: Coverage
    route: RouteInfo
    usage: UsageInfo
    warnings: list[str] = Field(default_factory=list)


class ConfigStatus(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    config_path: str
    config_present: bool
    default_provider: str
    configured_providers: list[str]
    delete_remote_files: bool | None
    ready: bool
    message: str
