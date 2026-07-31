"""Extract the first or last decoded video frame without overwriting output."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

SUPPORTED_SUFFIXES = {".avi", ".m4v", ".mkv", ".mov", ".mp4"}
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


class FrameError(RuntimeError):
    """Raised when a boundary frame cannot be extracted safely."""


def _run(command: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FrameError("Could not run the bundled ffmpeg process") from exc


def _duration(path: Path) -> float:
    result = _run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        timeout=30,
    )
    match = _DURATION_RE.search(result.stderr)
    if not match:
        raise FrameError(f"Could not read video duration: {path}")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise FrameError(f"Video duration must be positive: {path}")
    return duration


def extract(input_path: Path, output_path: Path, position: str) -> dict[str, object]:
    source = input_path.expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise FrameError(f"Unsupported or non-file video input: {source}")
    output = output_path.expanduser().resolve(strict=False)
    if output.suffix.lower() != ".png":
        raise FrameError("Boundary frame output must use the .png extension")
    if output.exists():
        raise FrameError(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    duration = _duration(source)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    temp_dir = Path(tempfile.mkdtemp(prefix=".boundary-frame-", dir=output.parent))
    partial = temp_dir / "frame.png"
    try:
        command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
        if position == "last":
            command.extend(["-sseof", f"-{min(duration, 1.0):g}"])
        command.extend(["-i", str(source)])
        if position == "last":
            command.extend(["-vf", "reverse"])
        command.extend(["-frames:v", "1", "-update", "1", str(partial)])
        result = _run(command)
        if (
            result.returncode != 0
            or not partial.is_file()
            or partial.stat().st_size == 0
        ):
            detail = result.stderr.strip()[-1000:]
            raise FrameError(f"Boundary frame extraction failed: {detail}")
        try:
            os.link(partial, output)
        except FileExistsError as exc:
            raise FrameError(
                f"Refusing to overwrite existing output: {output}"
            ) from exc
        return {
            "status": "ok",
            "input": str(source),
            "output": str(output),
            "position": position,
            "source_duration_seconds": duration,
            "bytes": output.stat().st_size,
        }
    finally:
        shutil.rmtree(temp_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract a collision-free first or last decoded video frame."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--position", choices=("first", "last"), required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = extract(args.input, args.output, args.position)
    except (OSError, FrameError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
