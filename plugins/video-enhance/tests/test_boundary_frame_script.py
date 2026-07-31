from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "create"
    / "scripts"
    / "extract_boundary_frame.py"
)


def _make_two_color_clip(path: Path) -> None:
    result = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=160x90:r=24:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x90:r=24:d=0.5",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def _average_rgb(path: Path) -> tuple[int, int, int]:
    result = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            "scale=1:1",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert len(result.stdout) == 3
    return tuple(result.stdout)


def test_extract_boundary_frames_preserves_temporal_ends(tmp_path: Path) -> None:
    video = tmp_path / "two-colors.mp4"
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    _make_two_color_clip(video)

    payloads: list[dict[str, object]] = []
    for position, output in (("first", first), ("last", last)):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--input",
                str(video),
                "--output",
                str(output),
                "--position",
                position,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        payloads.append(json.loads(result.stdout))

    first_rgb = _average_rgb(first)
    last_rgb = _average_rgb(last)
    assert first_rgb[0] > first_rgb[2]
    assert last_rgb[2] > last_rgb[0]
    assert [payload["position"] for payload in payloads] == ["first", "last"]
