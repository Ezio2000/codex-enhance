# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = [
#   "Pillow>=12.3,<13",
# ]
# ///
"""Create, edit, inspect, and verify animated GIF files deterministically."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageSequence, UnidentifiedImageError

CLI_VERSION = "1.0.0"
MANIFEST_SCHEMA = "image-enhance/gif-animation/v1"
RESULT_SCHEMA = "image-enhance/gif-result/v1"
SUPPORTED_FRAME_EXTENSIONS = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
)
MAX_FRAMES = 500
MAX_TOTAL_PIXELS = 100_000_000
MAX_DURATION_MS = 60_000
TRANSPARENCY_INDEX = 255
NATURAL_PARTS = re.compile(r"(\d+)")

Image.MAX_IMAGE_PIXELS = MAX_TOTAL_PIXELS


class GifPipelineError(Exception):
    """A stable, user-actionable pipeline error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _natural_key(path: Path) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in NATURAL_PARTS.split(path.name.casefold()):
        parts.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(parts)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GifPipelineError(
            "invalid_manifest", f"Cannot read valid JSON from {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GifPipelineError("invalid_manifest", "Manifest must be a JSON object.")
    return payload


def _resolve_input(path: str | Path, *, kind: str = "file") -> Path:
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise GifPipelineError(
            "input_not_found", f"Cannot resolve input: {path}"
        ) from exc
    if kind == "file" and not resolved.is_file():
        raise GifPipelineError("input_not_file", f"Input is not a file: {resolved}")
    if kind == "directory" and not resolved.is_dir():
        raise GifPipelineError(
            "input_not_directory", f"Input is not a directory: {resolved}"
        )
    return resolved


def _resolve_output(path: str | Path, *, overwrite: bool) -> Path:
    target = Path(path).expanduser().resolve(strict=False)
    if target.suffix.casefold() != ".gif":
        raise GifPipelineError("invalid_output", "Output path must end in .gif.")
    if target.exists() and not overwrite:
        raise GifPipelineError(
            "output_exists", f"Output already exists; pass --overwrite: {target}"
        )
    if target.exists() and not target.is_file():
        raise GifPipelineError("invalid_output", f"Output is not a file: {target}")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GifPipelineError(
            "output_parent_error", f"Cannot create output directory: {target.parent}"
        ) from exc
    return target


def _normalize_duration(value: int) -> tuple[int, bool]:
    if value <= 0 or value > MAX_DURATION_MS:
        raise GifPipelineError(
            "invalid_duration",
            f"Frame duration must be between 1 and {MAX_DURATION_MS} ms.",
        )
    normalized = max(10, int(round(value / 10.0) * 10))
    return normalized, normalized != value


def _parse_durations(
    raw: str | None, *, frame_count: int, default_ms: int
) -> tuple[list[int], list[str]]:
    if raw is None:
        requested = [default_ms] * frame_count
    else:
        try:
            requested = [int(part.strip()) for part in raw.split(",") if part.strip()]
        except ValueError as exc:
            raise GifPipelineError(
                "invalid_duration", "Durations must be comma-separated integers."
            ) from exc
        if len(requested) == 1:
            requested *= frame_count
        if len(requested) != frame_count:
            raise GifPipelineError(
                "duration_count_mismatch",
                f"Expected 1 or {frame_count} durations, received {len(requested)}.",
            )

    durations: list[int] = []
    rounded = False
    for value in requested:
        normalized, changed = _normalize_duration(value)
        durations.append(normalized)
        rounded = rounded or changed
    warnings = (
        ["GIF frame durations were rounded to 10 ms increments."] if rounded else []
    )
    return durations, warnings


def _validate_loop(loop: int) -> None:
    if loop < 0 or loop > 65_535:
        raise GifPipelineError(
            "invalid_loop", "Loop must be 0 for infinite or between 1 and 65535."
        )


def _validate_limits(frames: Sequence[Image.Image]) -> None:
    if not frames:
        raise GifPipelineError("no_frames", "No decodable frames were supplied.")
    if len(frames) > MAX_FRAMES:
        raise GifPipelineError(
            "too_many_frames", f"At most {MAX_FRAMES} frames are supported."
        )
    total_pixels = sum(frame.width * frame.height for frame in frames)
    if total_pixels > MAX_TOTAL_PIXELS:
        raise GifPipelineError(
            "too_many_pixels",
            f"Decoded frames exceed the {MAX_TOTAL_PIXELS} pixel safety limit.",
        )


def _open_still(path: Path) -> Image.Image:
    try:
        with Image.open(path) as source:
            source.load()
            return source.convert("RGBA")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise GifPipelineError(
            "invalid_frame", f"Cannot decode frame {path}: {exc}"
        ) from exc


def _load_frame_paths(paths: Sequence[Path]) -> list[Image.Image]:
    frames = [_open_still(path) for path in paths]
    _validate_limits(frames)
    return frames


def _paths_from_directory(directory: Path) -> list[Path]:
    paths = sorted(
        (
            path.resolve()
            for path in directory.iterdir()
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.casefold() in SUPPORTED_FRAME_EXTENSIONS
        ),
        key=_natural_key,
    )
    if not paths:
        raise GifPipelineError(
            "no_frames", f"No supported still-image frames found in {directory}."
        )
    return paths


def _paths_and_timing_from_manifest(
    manifest_path: Path,
) -> tuple[list[Path], list[int], int, list[str]]:
    payload = _json_object(manifest_path)
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise GifPipelineError(
            "invalid_manifest", f"Manifest schema must be {MANIFEST_SCHEMA!r}."
        )
    loop = payload.get("loop", 0)
    if not isinstance(loop, int):
        raise GifPipelineError("invalid_manifest", "Manifest loop must be an integer.")
    _validate_loop(loop)
    raw_frames = payload.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise GifPipelineError(
            "invalid_manifest", "Manifest frames must be a non-empty array."
        )
    if len(raw_frames) > MAX_FRAMES:
        raise GifPipelineError(
            "too_many_frames", f"At most {MAX_FRAMES} manifest frames are supported."
        )

    paths: list[Path] = []
    durations: list[int] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_frames, start=1):
        if not isinstance(item, dict):
            raise GifPipelineError(
                "invalid_manifest", f"Frame {index} must be an object."
            )
        raw_path = item.get("path")
        raw_duration = item.get("durationMs")
        if not isinstance(raw_path, str) or not isinstance(raw_duration, int):
            raise GifPipelineError(
                "invalid_manifest",
                f"Frame {index} requires string path and integer durationMs.",
            )
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = manifest_path.parent / candidate
        paths.append(_resolve_input(candidate))
        duration, changed = _normalize_duration(raw_duration)
        durations.append(duration)
        if (
            changed
            and "GIF frame durations were rounded to 10 ms increments." not in warnings
        ):
            warnings.append("GIF frame durations were rounded to 10 ms increments.")
    return paths, durations, loop, warnings


def _load_gif(path: Path) -> tuple[list[Image.Image], list[int], int]:
    try:
        with Image.open(path) as source:
            if source.format != "GIF":
                raise GifPipelineError("not_gif", f"Input is not a GIF: {path}")
            loop = int(source.info.get("loop", 1))
            frames: list[Image.Image] = []
            durations: list[int] = []
            for frame in ImageSequence.Iterator(source):
                frames.append(frame.convert("RGBA"))
                duration, _ = _normalize_duration(int(frame.info.get("duration", 100)))
                durations.append(duration)
    except GifPipelineError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise GifPipelineError(
            "invalid_gif", f"Cannot decode GIF {path}: {exc}"
        ) from exc
    _validate_limits(frames)
    return frames, durations, loop


def _resize_frames(
    frames: Sequence[Image.Image],
    *,
    width: int | None,
    height: int | None,
    pixel_art: bool,
) -> list[Image.Image]:
    if (width is None) != (height is None):
        raise GifPipelineError(
            "invalid_size", "Pass both --width and --height, or neither."
        )
    if width is not None and (width <= 0 or height is None or height <= 0):
        raise GifPipelineError("invalid_size", "Width and height must be positive.")

    target_size = (width, height) if width is not None and height is not None else None
    if target_size is None:
        sizes = {frame.size for frame in frames}
        if len(sizes) != 1:
            raise GifPipelineError(
                "frame_size_mismatch",
                "Frame dimensions differ; pass --width and --height to normalize them.",
            )
        return [frame.copy() for frame in frames]

    resampling = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    return [
        frame.copy()
        if frame.size == target_size
        else frame.resize(target_size, resampling)
        for frame in frames
    ]


def _global_palette(frames: Sequence[Image.Image], *, colors: int) -> Image.Image:
    if colors < 2 or colors > 256:
        raise GifPipelineError(
            "invalid_palette", "Palette colors must be between 2 and 256."
        )
    tile_size = 128
    columns = min(8, len(frames))
    rows = math.ceil(len(frames) / columns)
    sample = Image.new("RGB", (columns * tile_size, rows * tile_size), "white")
    for index, frame in enumerate(frames):
        tile = frame.copy()
        tile.thumbnail((tile_size, tile_size), Image.Resampling.LANCZOS)
        rgb = Image.new("RGB", tile.size, "white")
        rgb.paste(tile.convert("RGB"), mask=tile.getchannel("A"))
        x = (index % columns) * tile_size + (tile_size - tile.width) // 2
        y = (index // columns) * tile_size + (tile_size - tile.height) // 2
        sample.paste(rgb, (x, y))
    return sample.quantize(
        colors=colors - 1,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )


def _quantize_frames(
    frames: Sequence[Image.Image],
    *,
    colors: int,
    pixel_art: bool,
) -> list[Image.Image]:
    palette = _global_palette(frames, colors=colors)
    dither = Image.Dither.NONE if pixel_art else Image.Dither.FLOYDSTEINBERG
    encoded: list[Image.Image] = []
    for frame in frames:
        alpha = frame.getchannel("A")
        rgb = Image.new("RGB", frame.size, "white")
        rgb.paste(frame.convert("RGB"), mask=alpha)
        indexed = rgb.quantize(palette=palette, dither=dither)
        pixels = bytearray(indexed.tobytes())
        for offset, alpha_value in enumerate(alpha.tobytes()):
            if alpha_value < 128:
                pixels[offset] = TRANSPARENCY_INDEX
        indexed.frombytes(bytes(pixels))
        raw_palette = indexed.getpalette() or []
        raw_palette.extend([0] * (768 - len(raw_palette)))
        start = TRANSPARENCY_INDEX * 3
        raw_palette[start : start + 3] = [0, 0, 0]
        indexed.putpalette(raw_palette[:768])
        indexed.info["transparency"] = TRANSPARENCY_INDEX
        encoded.append(indexed)
    return encoded


def _save_gif(
    frames: Sequence[Image.Image],
    durations: Sequence[int],
    *,
    output: Path,
    loop: int,
    colors: int,
    pixel_art: bool,
) -> None:
    if len(frames) != len(durations):
        raise GifPipelineError(
            "internal_mismatch", "Frame and duration counts do not match."
        )
    _validate_loop(loop)
    indexed = _quantize_frames(frames, colors=colors, pixel_art=pixel_art)
    try:
        indexed[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=indexed[1:],
            duration=list(durations),
            loop=loop,
            disposal=2,
            transparency=TRANSPARENCY_INDEX,
            optimize=False,
        )
    except OSError as exc:
        raise GifPipelineError(
            "write_failed", f"Cannot write GIF {output}: {exc}"
        ) from exc


def inspect_gif(path: Path) -> dict[str, Any]:
    frames, durations, loop = _load_gif(path)
    width, height = frames[0].size
    return {
        "schema": RESULT_SCHEMA,
        "status": "ok",
        "inputPath": str(path),
        "width": width,
        "height": height,
        "frameCount": len(frames),
        "durationMs": sum(durations),
        "durationsMs": durations,
        "loop": loop,
        "bytes": path.stat().st_size,
        "warnings": [],
    }


def _result(output: Path, warnings: Sequence[str]) -> dict[str, Any]:
    result = inspect_gif(output)
    result.pop("inputPath")
    result["outputPath"] = str(output)
    result["warnings"] = list(warnings)
    return result


def _build_common(
    frames: Sequence[Image.Image],
    durations: Sequence[int],
    *,
    args: argparse.Namespace,
    loop: int,
    warnings: Sequence[str],
) -> dict[str, Any]:
    normalized = _resize_frames(
        frames,
        width=args.width,
        height=args.height,
        pixel_art=args.pixel_art,
    )
    _validate_limits(normalized)
    output = _resolve_output(args.output, overwrite=args.overwrite)
    _save_gif(
        normalized,
        durations,
        output=output,
        loop=loop,
        colors=args.colors,
        pixel_art=args.pixel_art,
    )
    return _result(output, warnings)


def command_build(args: argparse.Namespace) -> dict[str, Any]:
    if args.manifest:
        manifest = _resolve_input(args.manifest)
        paths, durations, loop, warnings = _paths_and_timing_from_manifest(manifest)
        if args.loop is not None:
            loop = args.loop
        frames = _load_frame_paths(paths)
    else:
        if args.source_dir:
            source = _resolve_input(args.source_dir, kind="directory")
            paths = _paths_from_directory(source)
        else:
            paths = [_resolve_input(path) for path in args.frame]
        frames = _load_frame_paths(paths)
        durations, warnings = _parse_durations(
            args.durations,
            frame_count=len(frames),
            default_ms=args.default_duration,
        )
        loop = 0 if args.loop is None else args.loop
    _validate_loop(loop)
    return _build_common(frames, durations, args=args, loop=loop, warnings=warnings)


def command_from_sheet(args: argparse.Namespace) -> dict[str, Any]:
    if args.columns <= 0 or args.rows <= 0:
        raise GifPipelineError("invalid_grid", "Columns and rows must be positive.")
    source_path = _resolve_input(args.source)
    sheet = _open_still(source_path)
    if sheet.width % args.columns or sheet.height % args.rows:
        raise GifPipelineError(
            "grid_not_divisible",
            f"Sheet {sheet.width}x{sheet.height} is not evenly divisible by "
            f"{args.columns} columns and {args.rows} rows.",
        )
    cell_width = sheet.width // args.columns
    cell_height = sheet.height // args.rows
    frames = [
        sheet.crop(
            (
                column * cell_width,
                row * cell_height,
                (column + 1) * cell_width,
                (row + 1) * cell_height,
            )
        )
        for row in range(args.rows)
        for column in range(args.columns)
    ]
    _validate_limits(frames)
    durations, warnings = _parse_durations(
        args.durations,
        frame_count=len(frames),
        default_ms=args.default_duration,
    )
    _validate_loop(args.loop)
    return _build_common(
        frames, durations, args=args, loop=args.loop, warnings=warnings
    )


def command_edit(args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve_input(args.source)
    frames, durations, original_loop = _load_gif(source)
    if args.speed <= 0:
        raise GifPipelineError("invalid_speed", "Speed must be greater than zero.")
    adjusted: list[int] = []
    warnings: list[str] = []
    for duration in durations:
        normalized, changed = _normalize_duration(max(1, round(duration / args.speed)))
        adjusted.append(normalized)
        if (
            changed
            and "GIF frame durations were rounded to 10 ms increments." not in warnings
        ):
            warnings.append("GIF frame durations were rounded to 10 ms increments.")
    loop = original_loop if args.loop is None else args.loop
    _validate_loop(loop)
    return _build_common(frames, adjusted, args=args, loop=loop, warnings=warnings)


def _add_encoding_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", required=True, help="Destination .gif path.")
    parser.add_argument("--width", type=int, help="Normalize all frames to this width.")
    parser.add_argument(
        "--height", type=int, help="Normalize all frames to this height."
    )
    parser.add_argument(
        "--colors",
        type=int,
        default=192,
        help="Global palette size including transparency (default: 192).",
    )
    parser.add_argument(
        "--pixel-art",
        action="store_true",
        help="Use nearest-neighbor scaling and disable dithering.",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing output file."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, edit, inspect, and verify animated GIF files."
    )
    parser.add_argument("--version", action="version", version=CLI_VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a GIF from image frames.")
    source = build.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-dir", help="Directory containing still-image frames.")
    source.add_argument(
        "--frame",
        action="append",
        default=[],
        help="Frame path; repeat in the required order.",
    )
    source.add_argument("--manifest", help="Animation manifest JSON path.")
    build.add_argument("--durations", help="One or comma-separated frame durations.")
    build.add_argument("--default-duration", type=int, default=100)
    build.add_argument(
        "--loop", type=int, help="0 for infinite; omit to use manifest or default."
    )
    _add_encoding_options(build)
    build.set_defaults(handler=command_build)

    sheet = subparsers.add_parser(
        "from-sheet", help="Build a row-major GIF from an evenly divided sprite sheet."
    )
    sheet.add_argument("--source", required=True, help="Sprite-sheet image path.")
    sheet.add_argument("--columns", required=True, type=int)
    sheet.add_argument("--rows", required=True, type=int)
    sheet.add_argument("--durations", help="One or comma-separated frame durations.")
    sheet.add_argument("--default-duration", type=int, default=100)
    sheet.add_argument("--loop", type=int, default=0)
    _add_encoding_options(sheet)
    sheet.set_defaults(handler=command_from_sheet)

    edit = subparsers.add_parser("edit", help="Resize or retime an existing GIF.")
    edit.add_argument("--source", required=True, help="Existing GIF path.")
    edit.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback multiplier; 2.0 is twice as fast.",
    )
    edit.add_argument("--loop", type=int, help="0 for infinite; omit to preserve.")
    _add_encoding_options(edit)
    edit.set_defaults(handler=command_edit)

    inspect = subparsers.add_parser("inspect", help="Inspect and verify a GIF.")
    inspect.add_argument("--source", required=True, help="GIF path.")
    inspect.set_defaults(handler=lambda args: inspect_gif(_resolve_input(args.source)))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except GifPipelineError as exc:
        print(
            json.dumps(
                {
                    "schema": RESULT_SCHEMA,
                    "status": "failed",
                    "error": {"code": exc.code, "message": str(exc)},
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
