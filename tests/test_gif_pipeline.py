from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image, ImageSequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "plugins"
    / "image-enhance"
    / "skills"
    / "create-gif"
    / "scripts"
    / "gif_pipeline.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("gif_pipeline", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gif_pipeline = _load_script()


def _write_frame(
    path: Path,
    color: tuple[int, int, int, int],
    *,
    size: tuple[int, int] = (24, 24),
) -> None:
    Image.new("RGBA", size, color).save(path)


def _run(args: list[str], capsys) -> tuple[int, dict]:
    exit_code = gif_pipeline.main(args)
    captured = capsys.readouterr()
    stream = captured.out if exit_code == 0 else captured.err
    return exit_code, json.loads(stream)


def test_build_uses_natural_order_and_variable_durations(
    tmp_path: Path, capsys
) -> None:
    frames = tmp_path / "frames"
    frames.mkdir()
    _write_frame(frames / "frame_1.png", (240, 20, 20, 255))
    _write_frame(frames / "frame_10.png", (20, 20, 240, 255))
    _write_frame(frames / "frame_2.png", (20, 240, 20, 255))
    output = tmp_path / "ordered.gif"

    exit_code, payload = _run(
        [
            "build",
            "--source-dir",
            str(frames),
            "--durations",
            "100,200,300",
            "--colors",
            "16",
            "--output",
            str(output),
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["frameCount"] == 3
    assert payload["durationsMs"] == [100, 200, 300]
    assert payload["loop"] == 0
    with Image.open(output) as source:
        colors = [
            frame.convert("RGB").getpixel((12, 12))
            for frame in ImageSequence.Iterator(source)
        ]
    assert colors == [(240, 20, 20), (20, 240, 20), (20, 20, 240)]


def test_from_sheet_builds_twelve_row_major_frames(tmp_path: Path, capsys) -> None:
    colors = [
        (20 + index * 15, 30 + index * 7, 220 - index * 11, 255) for index in range(12)
    ]
    sheet = Image.new("RGBA", (64, 48))
    for index, color in enumerate(colors):
        x = (index % 4) * 16
        y = (index // 4) * 16
        sheet.paste(color, (x, y, x + 16, y + 16))
    sheet_path = tmp_path / "sheet.png"
    sheet.save(sheet_path)
    output = tmp_path / "twelve.gif"

    exit_code, payload = _run(
        [
            "from-sheet",
            "--source",
            str(sheet_path),
            "--columns",
            "4",
            "--rows",
            "3",
            "--default-duration",
            "120",
            "--pixel-art",
            "--colors",
            "32",
            "--output",
            str(output),
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["width"] == 16
    assert payload["height"] == 16
    assert payload["frameCount"] == 12
    assert payload["durationMs"] == 1440
    with Image.open(output) as source:
        observed = [
            frame.convert("RGB").getpixel((8, 8))
            for frame in ImageSequence.Iterator(source)
        ]
    assert observed == [color[:3] for color in colors]


def test_manifest_resolves_unicode_relative_paths_and_rounds_duration(
    tmp_path: Path, capsys
) -> None:
    frame_dir = tmp_path / "帧"
    frame_dir.mkdir()
    _write_frame(frame_dir / "开始.png", (200, 40, 80, 255))
    _write_frame(frame_dir / "结束.png", (40, 80, 200, 255))
    manifest = {
        "schema": gif_pipeline.MANIFEST_SCHEMA,
        "loop": 2,
        "frames": [
            {"path": "帧/开始.png", "durationMs": 123},
            {"path": "帧/结束.png", "durationMs": 456},
        ],
    }
    manifest_path = tmp_path / "动画.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    output = tmp_path / "动画.gif"

    exit_code, payload = _run(
        [
            "build",
            "--manifest",
            str(manifest_path),
            "--output",
            str(output),
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["durationsMs"] == [120, 460]
    assert payload["durationMs"] == 580
    assert payload["loop"] == 2
    assert payload["warnings"] == [
        "GIF frame durations were rounded to 10 ms increments."
    ]


def test_edit_resizes_and_changes_playback_speed(tmp_path: Path, capsys) -> None:
    frames = tmp_path / "frames"
    frames.mkdir()
    _write_frame(frames / "1.png", (255, 0, 0, 255))
    _write_frame(frames / "2.png", (0, 0, 255, 255))
    source = tmp_path / "source.gif"
    edited = tmp_path / "edited.gif"

    assert (
        _run(
            [
                "build",
                "--source-dir",
                str(frames),
                "--durations",
                "200",
                "--output",
                str(source),
            ],
            capsys,
        )[0]
        == 0
    )
    exit_code, payload = _run(
        [
            "edit",
            "--source",
            str(source),
            "--speed",
            "2",
            "--width",
            "12",
            "--height",
            "12",
            "--output",
            str(edited),
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["width"] == 12
    assert payload["height"] == 12
    assert payload["durationsMs"] == [100, 100]
    assert payload["durationMs"] == 200


def test_transparent_frames_use_restore_background_disposal(
    tmp_path: Path, capsys
) -> None:
    frames = tmp_path / "transparent"
    frames.mkdir()
    for index in range(3):
        frame = Image.new("RGBA", (18, 6), (0, 0, 0, 0))
        frame.paste((250, 30, 30, 255), (index * 6, 0, index * 6 + 6, 6))
        frame.save(frames / f"{index}.png")
    output = tmp_path / "transparent.gif"

    exit_code, payload = _run(
        [
            "build",
            "--source-dir",
            str(frames),
            "--pixel-art",
            "--output",
            str(output),
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["frameCount"] == 3
    with Image.open(output) as source:
        decoded = [
            frame.convert("RGBA").copy() for frame in ImageSequence.Iterator(source)
        ]
    assert decoded[1].getpixel((2, 2))[3] == 0
    assert decoded[1].getpixel((8, 2))[3] == 255


def test_rejects_sprite_sheet_that_is_not_evenly_divisible(
    tmp_path: Path, capsys
) -> None:
    sheet_path = tmp_path / "bad-sheet.png"
    _write_frame(sheet_path, (0, 0, 0, 255), size=(65, 48))

    exit_code, payload = _run(
        [
            "from-sheet",
            "--source",
            str(sheet_path),
            "--columns",
            "4",
            "--rows",
            "3",
            "--output",
            str(tmp_path / "bad.gif"),
        ],
        capsys,
    )

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "grid_not_divisible"
    assert not (tmp_path / "bad.gif").exists()


def test_trim_small_normalizes_reported_generator_dimensions(
    tmp_path: Path, capsys
) -> None:
    colors = [
        (30 + index * 20, 210 - index * 15, 40 + index * 12, 255) for index in range(8)
    ]
    sheet = Image.new("RGBA", (1774, 887), (255, 0, 255, 255))
    for index, color in enumerate(colors):
        x = (index % 4) * 443
        y = (index // 4) * 443
        sheet.paste(color, (x, y, x + 443, y + 443))
    sheet_path = tmp_path / "generated-sheet.png"
    sheet.save(sheet_path)
    output = tmp_path / "trimmed.gif"

    exit_code, payload = _run(
        [
            "from-sheet",
            "--source",
            str(sheet_path),
            "--columns",
            "4",
            "--rows",
            "2",
            "--grid-fit",
            "trim-small",
            "--pixel-art",
            "--colors",
            "32",
            "--output",
            str(output),
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["width"] == 443
    assert payload["height"] == 443
    assert payload["frameCount"] == 8
    assert payload["sheetNormalization"] == {
        "sourceSize": [1774, 887],
        "normalizedSize": [1772, 886],
        "trimmedPixels": {"right": 2, "bottom": 1},
        "cellSize": [443, 443],
        "columns": 4,
        "rows": 2,
    }
    assert payload["warnings"] == [
        "Normalized sprite sheet by trimming right=2px and bottom=1px."
    ]


def test_trim_small_rejects_remainders_above_limit(tmp_path: Path, capsys) -> None:
    sheet_path = tmp_path / "too-wide.png"
    _write_frame(sheet_path, (20, 30, 40, 255), size=(110, 50))

    exit_code, payload = _run(
        [
            "from-sheet",
            "--source",
            str(sheet_path),
            "--columns",
            "8",
            "--rows",
            "2",
            "--grid-fit",
            "trim-small",
            "--output",
            str(tmp_path / "unsafe.gif"),
        ],
        capsys,
    )

    assert exit_code == 2
    assert payload["error"]["code"] == "grid_trim_exceeds_limit"
    assert not (tmp_path / "unsafe.gif").exists()
