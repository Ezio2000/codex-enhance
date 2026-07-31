"""Join ordered video segments without overwriting an existing output."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import imageio_ffmpeg

SUPPORTED_SUFFIXES = {".avi", ".m4v", ".mkv", ".mov", ".mp4"}
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_SIZE_RE = re.compile(r"\b(\d{2,5})x(\d{2,5})\b")
_FPS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s+fps\b")


@dataclass(frozen=True)
class VideoInfo:
    path: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    has_audio: bool


class StitchError(RuntimeError):
    """Raised when ordered segments cannot be joined safely."""


def _run(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StitchError("Could not run the bundled ffmpeg process") from exc


def _probe(path: Path) -> VideoInfo:
    result = _run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        timeout=30,
    )
    text = result.stderr
    duration_match = _DURATION_RE.search(text)
    video_line = next((line for line in text.splitlines() if "Video:" in line), "")
    size_match = _SIZE_RE.search(video_line)
    if not duration_match or not size_match:
        raise StitchError(f"Unreadable duration or video stream: {path}")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    width, height = (int(value) for value in size_match.groups())
    fps_match = _FPS_RE.search(video_line)
    fps = float(fps_match.group(1)) if fps_match else 30.0
    if duration <= 0 or width <= 0 or height <= 0 or not 0 < fps <= 120:
        raise StitchError(f"Invalid video metadata: {path}")
    return VideoInfo(
        path=str(path),
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio="Audio:" in text,
    )


def _concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def _duration_matches(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= max(0.35, expected * 0.05)


def _stream_copy(
    ffmpeg: str,
    inputs: list[Path],
    concat_file: Path,
    partial: Path,
) -> subprocess.CompletedProcess[str]:
    concat_file.write_text(
        "".join(f"file '{_concat_path(path)}'\n" for path in inputs),
        encoding="utf-8",
    )
    return _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(partial),
        ]
    )


def _normalized_transcode(
    ffmpeg: str,
    inputs: list[Path],
    infos: list[VideoInfo],
    partial: Path,
) -> subprocess.CompletedProcess[str]:
    width = infos[0].width - infos[0].width % 2
    height = infos[0].height - infos[0].height % 2
    fps = min(infos[0].fps, 60)
    command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    for path in inputs:
        command.extend(["-i", str(path)])

    filters: list[str] = []
    concat_inputs: list[str] = []
    for index, info in enumerate(infos):
        filters.append(
            f"[{index}:v:0]"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={fps:g},format=yuv420p,setpts=PTS-STARTPTS[v{index}]"
        )
        if info.has_audio:
            filters.append(
                f"[{index}:a:0]aresample=async=1:first_pts=0,"
                "aformat=sample_rates=48000:channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
        else:
            filters.append(
                "anullsrc=r=48000:cl=stereo,"
                f"atrim=duration={info.duration_seconds:g},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
        concat_inputs.append(f"[v{index}][a{index}]")
    filters.append(
        f"{''.join(concat_inputs)}concat=n={len(inputs)}:v=1:a=1[outv][outa]"
    )

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(partial),
        ]
    )
    return _run(command)


def stitch(inputs: list[Path], output: Path) -> dict[str, object]:
    if len(inputs) < 2:
        raise StitchError("At least two ordered input videos are required")
    resolved_inputs: list[Path] = []
    for raw_path in inputs:
        path = raw_path.expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise StitchError(f"Unsupported or non-file video input: {path}")
        resolved_inputs.append(path)

    output = output.expanduser().resolve(strict=False)
    if output.suffix.lower() != ".mp4":
        raise StitchError("Output must use the .mp4 extension")
    if output.exists():
        raise StitchError(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    infos = [_probe(path) for path in resolved_inputs]
    expected_duration = sum(info.duration_seconds for info in infos)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    temp_dir = Path(tempfile.mkdtemp(prefix=".video-stitch-", dir=output.parent))
    partial = temp_dir / "joined.mp4"
    warnings: list[str] = []
    strategy = "stream-copy"
    try:
        copy_result = _stream_copy(
            ffmpeg,
            resolved_inputs,
            temp_dir / "inputs.ffconcat",
            partial,
        )
        copy_info = _probe(partial) if copy_result.returncode == 0 else None
        if copy_info is None or not _duration_matches(
            copy_info.duration_seconds, expected_duration
        ):
            partial.unlink(missing_ok=True)
            strategy = "normalized-transcode"
            warnings.append(
                "Input streams were incompatible with verified stream-copy; "
                "joined with a high-quality local H.264/AAC transcode."
            )
            transcode_result = _normalized_transcode(
                ffmpeg,
                resolved_inputs,
                infos,
                partial,
            )
            if transcode_result.returncode != 0:
                detail = transcode_result.stderr.strip()[-1000:]
                raise StitchError(f"Normalized stitching failed: {detail}")

        final_info = _probe(partial)
        if not _duration_matches(final_info.duration_seconds, expected_duration):
            raise StitchError(
                "Joined duration does not match the sum of ordered segments"
            )
        try:
            os.link(partial, output)
        except FileExistsError as exc:
            raise StitchError(
                f"Refusing to overwrite existing output: {output}"
            ) from exc
        result = {
            "status": "ok",
            "output": str(output),
            "strategy": strategy,
            "inputs": [asdict(info) for info in infos],
            "bytes": output.stat().st_size,
            "duration_seconds": final_info.duration_seconds,
            "width": final_info.width,
            "height": final_info.height,
            "has_audio": final_info.has_audio,
            "warnings": warnings,
        }
        return result
    finally:
        shutil.rmtree(temp_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Join ordered local video segments into one collision-free MP4."
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("inputs", nargs="+", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = stitch(args.inputs, args.output)
    except (OSError, StitchError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
