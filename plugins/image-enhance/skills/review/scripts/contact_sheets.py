# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = [
#   "Pillow>=12.3,<13",
#   "pillow-heif>=1.5,<2",
# ]
# ///
"""Build and safely clean cross-platform contact sheets for image review."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import stat
import sys
import tempfile
import uuid
import warnings
from collections.abc import Iterable, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import PIL
from PIL import (
    Image,
    ImageCms,
    ImageDraw,
    ImageFont,
    ImageOps,
    UnidentifiedImageError,
)
from pillow_heif import register_heif_opener

CLI_VERSION = "1.0.0"
MANIFEST_SCHEMA = "image-enhance/review-manifest/v1"
MARKER_SCHEMA = "image-enhance/review-marker/v1"
MARKER_NAME = ".image-enhance-review.marker.json"
MANIFEST_NAME = "manifest.json"
OUTPUT_PREFIX = "image-enhance-review-"
SHEET_NAME_PATTERN = re.compile(r"sheet_[0-9]{3,}\.jpg")
SUPPORTED_EXTENSIONS = frozenset(
    {
        ".avif",
        ".bmp",
        ".dib",
        ".gif",
        ".heic",
        ".heif",
        ".hif",
        ".jfif",
        ".jpe",
        ".jpeg",
        ".jpg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
    }
)

register_heif_opener(thumbnails=False)


class ReviewError(Exception):
    """A stable, user-actionable CLI error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path, *, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(code, f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewError(code, f"Expected a JSON object in {path}.")
    return payload


def _is_reparse_point(path: Path) -> bool:
    """Detect Windows junctions and other reparse points on Python 3.11+."""

    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return bool(attributes & reparse_flag)


def _is_link_like(path: Path) -> bool:
    return path.is_symlink() or _is_reparse_point(path)


def _is_same_or_child(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _resolve_source(source: str | Path) -> Path:
    try:
        resolved = Path(source).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ReviewError(
            "source_not_found", f"Cannot resolve source directory: {source}"
        ) from exc
    if not resolved.is_dir():
        raise ReviewError(
            "source_not_directory", f"Source is not a directory: {resolved}"
        )
    return resolved


def _iter_source_files(source: Path, *, recursive: bool) -> Iterable[Path]:
    if not recursive:
        for path in source.iterdir():
            if path.is_file() and not path.is_symlink():
                yield path
        return

    for directory, dirnames, filenames in os.walk(source, followlinks=False):
        root = Path(directory)
        dirnames[:] = [name for name in dirnames if not _is_link_like(root / name)]
        for name in filenames:
            path = root / name
            if path.is_file() and not path.is_symlink():
                yield path


def _stable_files(source: Path, *, recursive: bool) -> list[Path]:
    return sorted(
        _iter_source_files(source, recursive=recursive),
        key=lambda path: (
            path.relative_to(source).as_posix().casefold(),
            path.relative_to(source).as_posix(),
        ),
    )


def _create_output_directory() -> Path:
    return Path(tempfile.mkdtemp(prefix=OUTPUT_PREFIX)).resolve()


def _validate_generated_target(target: Path) -> None:
    if _is_link_like(target):
        raise ReviewError(
            "unsafe_cleanup_target", "Refusing to clean a link or reparse point."
        )
    if not target.name.startswith(OUTPUT_PREFIX):
        raise ReviewError(
            "unsafe_cleanup_target",
            f"Generated directory does not have the required prefix: {target}",
        )

    resolved = target.resolve(strict=True)
    filesystem_root = Path(resolved.anchor).resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    dangerous = {filesystem_root, Path.home().resolve(), system_temp}
    if resolved in dangerous:
        raise ReviewError("unsafe_cleanup_target", f"Refusing to clean {resolved}.")
    if resolved.parent != system_temp:
        raise ReviewError(
            "unsafe_cleanup_target",
            "Generated directory must be a direct child of the system temp directory.",
        )


def _remove_owned_directory(
    target: Path,
    *,
    expected_session_id: str,
    require_manifest: bool,
) -> None:
    _validate_generated_target(target)
    marker_path = target / MARKER_NAME
    if _is_link_like(marker_path) or not marker_path.is_file():
        raise ReviewError("invalid_marker", "Marker must be a regular file.")
    marker = _read_json(marker_path, code="invalid_marker")

    if marker.get("schema") != MARKER_SCHEMA:
        raise ReviewError("invalid_marker", "Marker schema does not match.")
    if marker.get("sessionId") != expected_session_id:
        raise ReviewError("invalid_marker", "Marker session does not match.")
    try:
        marked_dir = Path(str(marker["generatedDir"])).resolve(strict=True)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise ReviewError("invalid_marker", "Marker generatedDir is invalid.") from exc
    if marked_dir != target.resolve(strict=True):
        raise ReviewError("invalid_marker", "Marker directory does not match.")

    allowed_names = {MARKER_NAME}
    if require_manifest:
        manifest_path = target / MANIFEST_NAME
        if _is_link_like(manifest_path) or not manifest_path.is_file():
            raise ReviewError("invalid_manifest", "Manifest must be a regular file.")
        manifest = _read_json(manifest_path, code="invalid_manifest")
        if manifest.get("schema") != MANIFEST_SCHEMA:
            raise ReviewError("invalid_manifest", "Manifest schema does not match.")
        if manifest.get("sessionId") != expected_session_id:
            raise ReviewError("invalid_manifest", "Manifest session does not match.")
        try:
            manifest_dir = Path(str(manifest["generatedDir"])).resolve(strict=True)
            source_dir = Path(str(manifest["sourceDir"])).resolve(strict=False)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise ReviewError(
                "invalid_manifest", "Manifest paths are invalid."
            ) from exc
        if manifest_dir != target.resolve(strict=True):
            raise ReviewError("invalid_manifest", "Manifest directory does not match.")
        if _is_same_or_child(source_dir, target.resolve(strict=True)):
            raise ReviewError(
                "unsafe_cleanup_target",
                "Generated directory must not contain the source directory.",
            )

        sheets = manifest.get("sheets")
        if not isinstance(sheets, list):
            raise ReviewError("invalid_manifest", "Manifest sheets must be a list.")
        allowed_names.add(MANIFEST_NAME)
        for sheet in sheets:
            if not isinstance(sheet, dict) or not isinstance(sheet.get("path"), str):
                raise ReviewError("invalid_manifest", "Manifest sheet path is invalid.")
            raw_sheet_path = Path(sheet["path"])
            if _is_link_like(raw_sheet_path):
                raise ReviewError(
                    "unsafe_cleanup_target",
                    "A contact sheet is a link or reparse point.",
                )
            try:
                sheet_path = raw_sheet_path.resolve(strict=True)
            except OSError as exc:
                raise ReviewError(
                    "invalid_manifest", "A manifest contact sheet does not exist."
                ) from exc
            if (
                sheet_path.parent != target.resolve(strict=True)
                or not SHEET_NAME_PATTERN.fullmatch(sheet_path.name)
                or not sheet_path.is_file()
            ):
                raise ReviewError(
                    "invalid_manifest",
                    "A contact sheet path is outside the review run.",
                )
            allowed_names.add(sheet_path.name)
    else:
        allowed_names.update(
            path.name
            for path in target.iterdir()
            if path.is_file() and SHEET_NAME_PATTERN.fullmatch(path.name)
        )
        manifest_path = target / MANIFEST_NAME
        if manifest_path.is_file() and not _is_link_like(manifest_path):
            allowed_names.add(MANIFEST_NAME)

    entries = list(target.iterdir())
    for entry in entries:
        if (
            entry.name not in allowed_names
            or _is_link_like(entry)
            or not entry.is_file()
        ):
            raise ReviewError(
                "unsafe_cleanup_target",
                f"Unexpected entry prevents cleanup: {entry.name}",
            )

    for entry in entries:
        if entry.name != MARKER_NAME:
            entry.unlink()
    marker_path.unlink()
    target.rmdir()


def _exception_details(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, UnidentifiedImageError):
        code = "unidentified"
    elif isinstance(
        exc, (Image.DecompressionBombError, Image.DecompressionBombWarning)
    ):
        code = "decompression_bomb"
    elif isinstance(exc, PermissionError):
        code = "permission_denied"
    elif (
        "truncated" in str(exc).casefold()
        or "broken data stream" in str(exc).casefold()
    ):
        code = "truncated"
    elif isinstance(exc, OSError):
        code = "decode_error"
    else:
        code = "decode_error"

    message = " ".join(str(exc).split()) or exc.__class__.__name__
    return code, message[:500]


def _alpha_channel(image: Image.Image) -> Image.Image | None:
    if "A" in image.getbands():
        return image.getchannel("A")
    if image.mode == "P" and "transparency" in image.info:
        return image.convert("RGBA").getchannel("A")
    return None


def _to_srgb(image: Image.Image) -> tuple[Image.Image, list[str]]:
    image_warnings: list[str] = []
    alpha = _alpha_channel(image)
    icc_profile = image.info.get("icc_profile")

    if icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            target_profile = ImageCms.createProfile("sRGB")
            rgb = ImageCms.profileToProfile(
                image,
                source_profile,
                target_profile,
                outputMode="RGB",
            )
        except (OSError, TypeError, ValueError):
            image_warnings.append("icc_to_srgb_failed")
            rgb = image.convert("RGB")
    else:
        rgb = image.convert("RGB")

    if alpha is None:
        return rgb, image_warnings

    flattened = Image.new("RGB", rgb.size, "white")
    flattened.paste(rgb, (0, 0), alpha)
    rgb.close()
    alpha.close()
    return flattened, image_warnings


def _load_tile(
    source_path: Path,
    *,
    image_id: str,
    tile_width: int,
    tile_height: int,
    label_height: int,
) -> tuple[Image.Image, dict[str, Any]]:
    content_height = tile_height - label_height
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source_path) as opened:
            opened.seek(0)
            opened.load()
            detected_format = opened.format or "UNKNOWN"
            oriented = ImageOps.exif_transpose(opened)
            working = oriented.copy()
            working.info.update(opened.info)

    try:
        source_width, source_height = working.size
        source_mode = working.mode
        normalized, image_warnings = _to_srgb(working)
    finally:
        working.close()

    try:
        normalized.thumbnail(
            (tile_width, content_height),
            Image.Resampling.LANCZOS,
        )
        content = Image.new("RGB", (tile_width, content_height), "#f2f2f2")
        offset = (
            (tile_width - normalized.width) // 2,
            (content_height - normalized.height) // 2,
        )
        content.paste(normalized, offset)
    finally:
        normalized.close()

    tile = Image.new("RGB", (tile_width, tile_height), "#202020")
    tile.paste(content, (0, 0))
    content.close()

    font_size = max(14, min(32, round(label_height * 0.55)))
    font = ImageFont.load_default(size=font_size)
    draw = ImageDraw.Draw(tile)
    text_box = draw.textbbox((0, 0), image_id, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    draw.text(
        (
            (tile_width - text_width) // 2,
            content_height + (label_height - text_height) // 2 - text_box[1],
        ),
        image_id,
        fill="white",
        font=font,
    )

    return tile, {
        "detectedFormat": detected_format,
        "sourceWidth": source_width,
        "sourceHeight": source_height,
        "sourceMode": source_mode,
        "warnings": image_warnings,
    }


def _decoder_capabilities() -> dict[str, Any]:
    Image.init()
    registered = Image.registered_extensions()
    supported = {
        extension: registered.get(extension, "")
        for extension in sorted(SUPPORTED_EXTENSIONS)
        if extension in registered
    }
    return {
        "pillowVersion": PIL.__version__,
        "pillowHeifVersion": version("pillow-heif"),
        "registeredExtensions": supported,
    }


def build_contact_sheets(
    source: str | Path,
    *,
    recursive: bool = False,
    grid_size: int = 3,
    sheet_width: int = 1536,
    sheet_height: int = 1536,
    gap: int = 4,
) -> dict[str, Any]:
    """Build contact sheets and return their machine-readable summary."""

    if not 2 <= grid_size <= 8:
        raise ReviewError("invalid_grid_size", "grid_size must be between 2 and 8.")
    if not 512 <= sheet_width <= 8192 or not 512 <= sheet_height <= 8192:
        raise ReviewError(
            "invalid_sheet_size", "Sheet dimensions must be 512 through 8192."
        )
    if not 0 <= gap <= 32:
        raise ReviewError("invalid_gap", "gap must be between 0 and 32.")

    source_dir = _resolve_source(source)
    all_files = _stable_files(source_dir, recursive=recursive)
    candidates = [
        path for path in all_files if path.suffix.casefold() in SUPPORTED_EXTENSIONS
    ]

    tile_width = (sheet_width - gap * (grid_size + 1)) // grid_size
    tile_height = (sheet_height - gap * (grid_size + 1)) // grid_size
    label_height = max(26, min(54, round(tile_height * 0.1)))
    if tile_width < 128 or tile_height - label_height < 128:
        raise ReviewError(
            "thumbnail_too_small",
            "The requested grid and sheet size leave less than 128 px "
            "for image content.",
        )

    output_dir = _create_output_directory()
    session_id = str(uuid.uuid4())
    marker_written = False
    try:
        if _is_same_or_child(output_dir, source_dir):
            raise ReviewError(
                "temporary_output_inside_source",
                "The system temporary directory falls inside the selected source.",
            )

        _write_json(
            output_dir / MARKER_NAME,
            {
                "schema": MARKER_SCHEMA,
                "sessionId": session_id,
                "generatedDir": str(output_dir),
            },
        )
        marker_written = True

        sheets: list[dict[str, Any]] = []
        images: list[dict[str, Any]] = []
        invalid_images: list[dict[str, Any]] = []
        capacity = grid_size * grid_size
        sheet: Image.Image | None = None
        sheet_ids: list[str] = []
        sheet_index = 0
        position = 0

        def save_current_sheet() -> None:
            nonlocal sheet, sheet_ids, position
            if sheet is None:
                return
            sheet_path = output_dir / f"sheet_{sheet_index:03d}.jpg"
            sheet.save(
                sheet_path,
                format="JPEG",
                quality=85,
                optimize=True,
                progressive=True,
                subsampling="4:2:0",
            )
            sheet.close()
            sheets.append(
                {
                    "index": sheet_index,
                    "path": str(sheet_path),
                    "imageCount": len(sheet_ids),
                    "imageIds": list(sheet_ids),
                }
            )
            sheet = None
            sheet_ids = []
            position = 0

        for source_path in candidates:
            image_id = f"IMG_{len(images) + 1:05d}"
            try:
                tile, metadata = _load_tile(
                    source_path,
                    image_id=image_id,
                    tile_width=tile_width,
                    tile_height=tile_height,
                    label_height=label_height,
                )
            except Exception as exc:  # keep one bad image from aborting the folder
                error_code, reason = _exception_details(exc)
                invalid_images.append(
                    {
                        "sourcePath": str(source_path.resolve()),
                        "relativePath": source_path.relative_to(source_dir).as_posix(),
                        "sourceExtension": source_path.suffix.casefold(),
                        "errorCode": error_code,
                        "reason": reason,
                    }
                )
                continue

            if sheet is None:
                sheet_index += 1
                sheet = Image.new("RGB", (sheet_width, sheet_height), "#181818")

            row, column = divmod(position, grid_size)
            x = gap + column * (tile_width + gap)
            y = gap + row * (tile_height + gap)
            sheet.paste(tile, (x, y))
            tile.close()

            images.append(
                {
                    "id": image_id,
                    "sourcePath": str(source_path.resolve()),
                    "relativePath": source_path.relative_to(source_dir).as_posix(),
                    "sourceName": source_path.name,
                    "sourceExtension": source_path.suffix.casefold(),
                    "sheetIndex": sheet_index,
                    "position": position + 1,
                    "row": row + 1,
                    "column": column + 1,
                    **metadata,
                }
            )
            sheet_ids.append(image_id)
            position += 1
            if position == capacity:
                save_current_sheet()

        save_current_sheet()

        manifest = {
            "schema": MANIFEST_SCHEMA,
            "sessionId": session_id,
            "generatedAtUtc": datetime.now(UTC).isoformat(),
            "sourceDir": str(source_dir),
            "generatedDir": str(output_dir),
            "recursive": recursive,
            "gridSize": grid_size,
            "sheetWidth": sheet_width,
            "sheetHeight": sheet_height,
            "tileWidth": tile_width,
            "tileHeight": tile_height,
            "totalFiles": len(all_files),
            "nonImageFiles": len(all_files) - len(candidates),
            "candidateFiles": len(candidates),
            "acceptedImages": len(images),
            "invalidImageCount": len(invalid_images),
            "supportedExtensions": sorted(SUPPORTED_EXTENSIONS),
            "decoderCapabilities": _decoder_capabilities(),
            "sheets": sheets,
            "images": images,
            "invalidImages": invalid_images,
        }
        manifest_path = output_dir / MANIFEST_NAME
        _write_json(manifest_path, manifest)
        return {
            "status": "ok" if images else "no_decodable_images",
            "manifestPath": str(manifest_path),
            "generatedDir": str(output_dir),
            "sheetCount": len(sheets),
            "acceptedImages": len(images),
            "invalidImages": len(invalid_images),
        }
    except Exception:
        if output_dir.exists():
            if marker_written:
                with suppress(Exception):
                    _remove_owned_directory(
                        output_dir,
                        expected_session_id=session_id,
                        require_manifest=False,
                    )
            else:
                with suppress(OSError):
                    output_dir.rmdir()
        raise


def cleanup_manifest(manifest: str | Path) -> dict[str, Any]:
    """Remove one generated review directory after validating its ownership."""

    raw_manifest = Path(manifest).expanduser()
    if _is_link_like(raw_manifest) or _is_link_like(raw_manifest.parent):
        raise ReviewError(
            "unsafe_cleanup_target", "Refusing to clean through a symlink."
        )
    try:
        manifest_path = raw_manifest.resolve(strict=True)
    except OSError as exc:
        raise ReviewError(
            "manifest_not_found", f"Manifest not found: {manifest}"
        ) from exc
    if manifest_path.name != MANIFEST_NAME:
        raise ReviewError("invalid_manifest", f"Expected a {MANIFEST_NAME} path.")

    payload = _read_json(manifest_path, code="invalid_manifest")
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise ReviewError("invalid_manifest", "Manifest schema does not match.")
    session_id = payload.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        raise ReviewError("invalid_manifest", "Manifest sessionId is missing.")

    target = manifest_path.parent
    _remove_owned_directory(
        target,
        expected_session_id=session_id,
        require_manifest=True,
    )
    return {"status": "removed", "generatedDir": str(target)}


def _bounded_int(name: str, minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer.") from exc
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum} and {maximum}."
            )
        return parsed

    return parse


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and clean labeled image contact sheets.",
    )
    parser.add_argument("--version", action="version", version=CLI_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Build contact sheets.")
    build.add_argument("--source", required=True, help="Folder containing images.")
    build.add_argument("--recursive", action="store_true", help="Include subfolders.")
    build.add_argument(
        "--grid-size",
        type=_bounded_int("grid-size", 2, 8),
        default=3,
    )
    build.add_argument(
        "--sheet-width",
        type=_bounded_int("sheet-width", 512, 8192),
        default=1536,
    )
    build.add_argument(
        "--sheet-height",
        type=_bounded_int("sheet-height", 512, 8192),
        default=1536,
    )
    build.add_argument("--gap", type=_bounded_int("gap", 0, 32), default=4)

    cleanup = commands.add_parser(
        "cleanup", help="Remove a generated review directory."
    )
    cleanup.add_argument(
        "--manifest", required=True, help="Generated manifest.json path."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_contact_sheets(
                args.source,
                recursive=args.recursive,
                grid_size=args.grid_size,
                sheet_width=args.sheet_width,
                sheet_height=args.sheet_height,
                gap=args.gap,
            )
        else:
            result = cleanup_manifest(args.manifest)
    except ReviewError as exc:
        print(
            json.dumps(
                {"status": "error", "errorCode": exc.code, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "errorCode": "internal_error",
                    "error": " ".join(str(exc).split())[:500],
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
