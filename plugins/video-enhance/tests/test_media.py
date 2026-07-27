from pathlib import Path

import pytest

from video_enhance_mcp.core.media import resolve_video_path
from video_enhance_mcp.errors import MediaError


def test_resolve_video_path_accepts_unicode_and_spaces(tmp_path: Path) -> None:
    video = tmp_path / "中文 录屏.mov"
    video.write_bytes(b"placeholder")
    assert resolve_video_path(str(video), (tmp_path.resolve(),)) == video.resolve()


def test_resolve_video_path_rejects_outside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside.mov"
    allowed.mkdir()
    outside.write_bytes(b"placeholder")
    with pytest.raises(MediaError, match="outside configured allowed roots"):
        resolve_video_path(str(outside), (allowed.resolve(),))


def test_resolve_video_path_rejects_non_video_extension(tmp_path: Path) -> None:
    document = tmp_path / "secret.txt"
    document.write_text("not a video", encoding="utf-8")
    with pytest.raises(MediaError, match="Unsupported video extension"):
        resolve_video_path(str(document), (tmp_path.resolve(),))
