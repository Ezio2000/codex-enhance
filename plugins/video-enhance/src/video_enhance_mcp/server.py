"""stdio MCP entry point for provider-extensible video understanding."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from .config import config_path, load_settings
from .core.pipeline import VideoPipeline
from .core.profiles import AnalysisOperation, RequestedProfile
from .core.schemas import ConfigStatus, VideoAnalyzeResult, VideoInspectResult
from .errors import ConfigurationError, VideoEnhanceError

mcp = FastMCP(
    "Video Enhance",
    instructions=(
        "Inspect local videos first, then analyze through a configured provider. "
        "The server uses stdio, creates an audio-free MP4 proxy, validates structured "
        "results and timestamps, and reports partial results plus remote retention "
        "or cleanup warnings explicitly."
    ),
)


@mcp.tool()
async def video_config_status() -> ConfigStatus:
    """Report readiness and remote deletion policy without exposing secrets."""

    path = config_path()
    try:
        settings = load_settings(require_file=False)
        configured = sorted(
            name for name, item in settings.providers.items() if item.enabled
        )
        default = settings.providers.get(settings.default_provider)
        ready = bool(default and default.enabled and default.api_key)
        return ConfigStatus(
            config_path=str(path),
            config_present=path.is_file(),
            default_provider=settings.default_provider,
            configured_providers=configured,
            delete_remote_files=settings.security.delete_remote_files,
            ready=ready,
            message="Ready" if ready else f"Create or complete {path}",
        )
    except ConfigurationError as exc:
        return ConfigStatus(
            config_path=str(path),
            config_present=path.is_file(),
            default_provider="minimax",
            configured_providers=[],
            delete_remote_files=None,
            ready=False,
            message=str(exc),
        )


@mcp.tool()
async def video_inspect(
    video_path: Annotated[
        str,
        Field(
            min_length=1, description="Absolute local MP4, MOV, AVI, MKV, or M4V path."
        ),
    ],
) -> VideoInspectResult:
    """Inspect a local video without uploading it or consuming provider quota."""

    try:
        return await VideoPipeline(load_settings(require_file=False)).inspect(
            video_path
        )
    except VideoEnhanceError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def video_analyze(
    video_path: Annotated[
        str,
        Field(min_length=1, description="Absolute video path inside an allowed root."),
    ],
    ctx: Context,
    operation: AnalysisOperation = "summary",
    prompt: Annotated[
        str,
        Field(
            max_length=6000, description="Question or task; required for question mode."
        ),
    ] = "",
    profile: RequestedProfile = "auto",
    provider: Annotated[
        str,
        Field(
            min_length=1, max_length=80, description="Configured provider name or auto."
        ),
    ] = "auto",
) -> VideoAnalyzeResult:
    """Normalize, analyze, validate, and return a provider-neutral result."""

    if operation == "question" and not prompt.strip():
        raise ToolError("prompt is required when operation='question'")

    async def report(progress: float, message: str) -> None:
        await ctx.report_progress(progress=progress, total=1.0, message=message)

    try:
        return await VideoPipeline(load_settings(require_file=True)).analyze(
            video_path=video_path,
            operation=operation,
            prompt=prompt,
            requested_profile=profile,
            requested_provider=provider,
            progress=report,
        )
    except VideoEnhanceError as exc:
        await ctx.error(str(exc))
        raise ToolError(str(exc)) from exc
    except Exception as exc:
        await ctx.error(f"Unexpected video pipeline failure: {type(exc).__name__}")
        raise ToolError(
            "Unexpected video pipeline failure; no provider credentials were logged"
        ) from exc


def main() -> None:
    """Run exclusively over stdin/stdout; no TCP listener is created."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
