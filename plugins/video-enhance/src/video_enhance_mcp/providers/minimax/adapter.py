"""MiniMax implementation of the generic VideoProvider contract."""

from __future__ import annotations

from dataclasses import dataclass

from ...config import ProviderSettings
from ...core.contracts import (
    PreparedVideo,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
)
from ...core.prompts import build_video_prompt
from ...errors import ConfigurationError
from .client import MiniMaxClient


@dataclass(frozen=True, slots=True)
class MiniMaxProfile:
    detail: str
    fps: float
    max_completion_tokens: int = 4000


PROFILES = {
    "balanced": MiniMaxProfile("default", 1.0),
    "temporal": MiniMaxProfile("default", 5.0),
    "ocr": MiniMaxProfile("high", 1.0),
}


class MiniMaxProvider:
    name = "minimax"

    def __init__(
        self, settings: ProviderSettings, *, delete_remote_files: bool
    ) -> None:
        if settings.api_key is None:
            raise ConfigurationError("MiniMax api_key is required")
        self.api_key = settings.api_key
        self.base_url = settings.base_url or "https://api.minimaxi.com/v1"
        self.model = settings.model or "MiniMax-M3"
        self.delete_remote_files = delete_remote_files

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_formats=("mp4",),
            max_upload_bytes=512 * 1024 * 1024,
            supports_audio=False,
            supports_structured_output=True,
            supports_remote_url=False,
            min_fps=0.2,
            max_fps=5.0,
            detail_levels=("default", "high"),
        )

    async def analyze(
        self, media: PreparedVideo, request: ProviderRequest
    ) -> ProviderResponse:
        profile = PROFILES[request.profile]
        warnings: list[str] = []
        async with MiniMaxClient(
            base_url=self.base_url, api_key=self.api_key
        ) as client:
            async with client.temporary_upload(
                media.path, delete_remote=self.delete_remote_files
            ) as uploaded:
                completion = await client.analyze_video(
                    uploaded.file_id,
                    model=self.model,
                    prompt=build_video_prompt(request.prompt, request.duration_ms),
                    detail=profile.detail,
                    fps=profile.fps,
                    max_completion_tokens=profile.max_completion_tokens,
                )
            if uploaded.cleanup_warning:
                warnings.append(uploaded.cleanup_warning)
        usage = completion.usage
        return ProviderResponse(
            content=completion.content,
            model=self.model,
            detail=profile.detail,
            fps=profile.fps,
            structured=completion.structured_via_tool,
            usage=ProviderUsage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                latency_ms=completion.latency_ms,
                finish_reason=completion.finish_reason,
            ),
            warnings=warnings,
        )
