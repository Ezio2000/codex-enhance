"""Provider-neutral orchestration, validation, and result shaping."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import ValidationError

from ..config import Settings
from ..providers.registry import create_provider
from .contracts import ProviderRequest
from .media import MediaNormalizer
from .profiles import (
    DEFAULT_PROMPTS,
    AnalysisOperation,
    RequestedProfile,
    resolve_profile,
)
from .schemas import (
    AnalysisPayload,
    RouteInfo,
    UsageInfo,
    VideoAnalyzeResult,
    VideoInspectResult,
)
from .validation import parse_analysis_payload, validate_coverage

ProgressCallback = Callable[[float, str], Awaitable[None]]


async def _noop_progress(_: float, __: str) -> None:
    return None


class VideoPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.normalizer = MediaNormalizer(settings.allowed_roots)

    async def inspect(self, video_path: str) -> VideoInspectResult:
        media = await self.normalizer.inspect(video_path)
        return VideoInspectResult(media=media, normalization_required=True)

    async def analyze(
        self,
        *,
        video_path: str,
        operation: AnalysisOperation,
        prompt: str,
        requested_profile: RequestedProfile,
        requested_provider: str = "auto",
        progress: ProgressCallback | None = None,
    ) -> VideoAnalyzeResult:
        report = progress or _noop_progress
        effective_prompt = prompt.strip() or DEFAULT_PROMPTS[operation]
        profile = resolve_profile(operation, requested_profile)
        provider_name, provider = create_provider(self.settings, requested_provider)
        capabilities = provider.capabilities()
        runtime_limit = self.settings.runtime.max_upload_mb * 1024 * 1024
        upload_limit = min(runtime_limit, capabilities.max_upload_bytes)

        await report(0.05, "检查视频和访问范围")
        async with self.normalizer.prepare(
            video_path, max_upload_bytes=upload_limit
        ) as prepared:
            await report(0.40, "已生成 provider-safe 视觉代理 MP4")
            await report(0.50, f"调用 {provider_name} 分析视频")
            response = await provider.analyze(
                prepared,
                ProviderRequest(
                    prompt=effective_prompt,
                    duration_ms=prepared.metadata.source.duration_ms,
                    profile=profile,
                ),
            )
            warnings = list(response.warnings)
            status: Literal["completed", "partial"] = "completed"
            if response.usage.finish_reason not in {"stop", "tool_calls"}:
                warnings.append(
                    f"provider finish_reason was {response.usage.finish_reason!r}, not a normal stop"
                )
                status = "partial"

            await report(0.90, "校验结构化结果和时间戳")
            try:
                parse_warnings: list[str] = []
                analysis = parse_analysis_payload(response.content, parse_warnings)
                warnings.extend(parse_warnings)
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                warnings.append(f"provider JSON failed validation: {exc}")
                analysis = AnalysisPayload(
                    summary=f"{provider_name} returned an unvalidated partial response",
                    answer=response.content[:6000],
                    uncertainties=[
                        "The provider response did not match the analysis contract."
                    ],
                )
                status = "partial"

            coverage, coverage_warnings = validate_coverage(
                analysis,
                prepared.metadata.source.duration_ms,
                require_full_coverage=operation in {"summary", "timeline"},
            )
            if coverage_warnings:
                warnings.extend(coverage_warnings)
                status = "partial"
            usage = response.usage
            result = VideoAnalyzeResult(
                status=status,
                analysis=analysis,
                media=prepared.metadata,
                coverage=coverage,
                route=RouteInfo(
                    provider=provider_name,
                    model=response.model,
                    profile=profile,
                    detail=response.detail,
                    fps=response.fps,
                    structured_output=response.structured,
                ),
                usage=UsageInfo(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    total_tokens=usage.total_tokens,
                    latency_ms=usage.latency_ms,
                    finish_reason=usage.finish_reason,
                ),
                warnings=warnings,
            )
            await report(1.0, "完成")
            return result
