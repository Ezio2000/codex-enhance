"""Local access, probing, hashing, and provider-safe MP4 generation."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import imageio_ffmpeg

from ..errors import MediaError
from .contracts import PreparedVideo
from .schemas import MediaInfo, PreparedMedia

SUPPORTED_INPUT_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_SIZE_RE = re.compile(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b")
_AUDIO_RE = re.compile(r"Stream #.*?Audio:", re.IGNORECASE)


def resolve_video_path(raw_path: str, allowed_roots: tuple[Path, ...]) -> Path:
    candidate = Path(raw_path).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise MediaError(f"Video file not found or inaccessible: {candidate}") from exc
    if not resolved.is_file():
        raise MediaError(f"Video source is not a regular file: {resolved}")
    if not any(
        resolved == root or resolved.is_relative_to(root) for root in allowed_roots
    ):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise MediaError(f"Video path is outside configured allowed roots: {roots}")
    if resolved.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise MediaError(f"Unsupported video extension; expected one of: {supported}")
    return resolved


def _ffmpeg_probe_text(path: Path) -> str:
    try:
        completed = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError("Could not launch the bundled ffmpeg media probe") from exc
    return completed.stderr


def probe_video(path: Path) -> MediaInfo:
    text = _ffmpeg_probe_text(path)
    duration_ms = None
    width = height = None
    if match := _DURATION_RE.search(text):
        hours, minutes, seconds = match.groups()
        duration_ms = round(
            (int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000
        )
    if match := _VIDEO_SIZE_RE.search(text):
        width, height = (int(value) for value in match.groups())
    if "Video:" not in text:
        raise MediaError("The source does not contain a readable video stream")
    return MediaInfo(
        path=str(path),
        size_bytes=path.stat().st_size,
        duration_ms=duration_ms,
        width=width,
        height=height,
        container=path.suffix.lower().lstrip("."),
        has_audio=bool(_AUDIO_RE.search(text)),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonicalize(source: Path, output: Path, duration_ms: int | None) -> None:
    total_ms = duration_ms if duration_ms is not None else -1
    video_filter = (
        "scale=w='min(1920,iw)':h='min(1920,ih)':force_original_aspect_ratio=decrease,"
        "scale=w='trunc(iw/2)*2':h='trunc(ih/2)*2',setsar=1,setpts=PTS-STARTPTS,"
        "fps=30,pad=iw:ih+64:0:0:black,drawtext=fontcolor=white:fontsize=30:x=16:y=h-46:"
        f"text='SOURCE_TIME %{{pts\\:hms}}   TOTAL_MS {total_ms}'"
    )
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        str(output),
    ]
    timeout = min(max(120, int((duration_ms or 60_000) / 1000 * 10)), 3600)
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Video normalization timed out") from exc
    except OSError as exc:
        raise MediaError("Could not launch the bundled ffmpeg normalizer") from exc
    if completed.returncode != 0 or not output.is_file():
        detail = completed.stderr.strip()[-1500:] or "unknown ffmpeg failure"
        raise MediaError(f"Video normalization failed: {detail}")


class MediaNormalizer:
    """Create an audio-free H.264 MP4 visual proxy accepted by providers."""

    def __init__(self, allowed_roots: tuple[Path, ...]) -> None:
        self.allowed_roots = allowed_roots

    async def inspect(self, raw_path: str) -> MediaInfo:
        return await asyncio.to_thread(
            probe_video, resolve_video_path(raw_path, self.allowed_roots)
        )

    @asynccontextmanager
    async def prepare(
        self, raw_path: str, *, max_upload_bytes: int
    ) -> AsyncIterator[PreparedVideo]:
        source = resolve_video_path(raw_path, self.allowed_roots)
        source_info, source_hash = await asyncio.gather(
            asyncio.to_thread(probe_video, source),
            asyncio.to_thread(sha256_file, source),
        )
        with tempfile.TemporaryDirectory(prefix="video-enhance-") as temp_dir:
            os.chmod(temp_dir, 0o700)
            output = Path(temp_dir) / "visual-proxy.mp4"
            await asyncio.to_thread(
                _canonicalize, source, output, source_info.duration_ms
            )
            output_info = await asyncio.to_thread(probe_video, output)
            if output.stat().st_size > max_upload_bytes:
                raise MediaError(
                    f"Normalized video exceeds the selected provider limit of {max_upload_bytes} bytes"
                )
            if (
                source_info.duration_ms is not None
                and output_info.duration_ms is not None
            ):
                drift = abs(source_info.duration_ms - output_info.duration_ms)
                if drift > max(250, round(source_info.duration_ms * 0.01)):
                    raise MediaError(
                        f"Normalization changed duration by {drift} ms; timestamps are unsafe"
                    )
            yield PreparedVideo(
                path=output,
                metadata=PreparedMedia(
                    source=source_info,
                    upload_size_bytes=output.stat().st_size,
                    normalized=True,
                    normalizer="bundled-ffmpeg-h264-yuv420p-cfr30-timestamp-bar",
                    source_sha256=source_hash,
                ),
                output_duration_ms=output_info.duration_ms,
            )
