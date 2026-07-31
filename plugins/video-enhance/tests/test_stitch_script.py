from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import pytest

SCRIPT_PATH = (
    Path(__file__).parents[1] / "skills" / "create" / "scripts" / "stitch_videos.py"
)


def _load_stitch_module():
    spec = importlib.util.spec_from_file_location("stitch_videos", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_clip(path: Path, color: str) -> None:
    result = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x180:r=24:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_stitch_videos_joins_ordered_compatible_segments(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    output = tmp_path / "joined.mp4"
    _make_clip(first, "red")
    _make_clip(second, "blue")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--output",
            str(output),
            str(first),
            str(second),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["strategy"] == "stream-copy"
    assert payload["duration_seconds"] == pytest.approx(1.0, abs=0.15)
    assert payload["width"] == 320
    assert payload["height"] == 180
    assert payload["has_audio"] is True
    assert output.stat().st_size == payload["bytes"]


def test_stitch_videos_refuses_to_overwrite(tmp_path: Path) -> None:
    module = _load_stitch_module()
    output = tmp_path / "existing.mp4"
    output.write_bytes(b"keep")

    with pytest.raises(module.StitchError, match="Refusing to overwrite"):
        module.stitch([output, output], output)

    assert output.read_bytes() == b"keep"
