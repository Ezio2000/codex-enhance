from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "plugins"
    / "image-enhance"
    / "skills"
    / "review"
    / "scripts"
    / "contact_sheets.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("contact_sheets", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contact_sheets = _load_script()


def _write_image(path: Path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (80, 60), color).save(path)


def test_build_maps_images_and_cleans_up(tmp_path: Path) -> None:
    source = tmp_path / "源 images"
    source.mkdir()
    _write_image(source / "a.png", (255, 0, 0, 255))
    _write_image(source / "B.PNG", (0, 255, 0, 255))
    _write_image(source / "c.webp", (0, 0, 255, 255))
    _write_image(source / "透明.png", (255, 0, 255, 80))
    (source / "notes.txt").write_text("not an image", encoding="utf-8")
    (source / "broken.jpg").write_bytes(b"not really a jpeg")

    result = contact_sheets.build_contact_sheets(
        source,
        grid_size=2,
    )
    manifest_path = Path(result["manifestPath"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["status"] == "ok"
    assert result["sheetCount"] == 1
    assert manifest["acceptedImages"] == 4
    assert manifest["invalidImageCount"] == 1
    assert manifest["nonImageFiles"] == 1
    assert [item["id"] for item in manifest["images"]] == [
        "IMG_00001",
        "IMG_00002",
        "IMG_00003",
        "IMG_00004",
    ]
    assert {item["relativePath"] for item in manifest["images"]} == {
        "a.png",
        "B.PNG",
        "c.webp",
        "透明.png",
    }
    sheet_path = Path(manifest["sheets"][0]["path"])
    assert sheet_path.is_file()
    with Image.open(sheet_path) as sheet:
        assert sheet.size == (1536, 1536)

    generated_dir = Path(manifest["generatedDir"])
    cleanup = contact_sheets.cleanup_manifest(manifest_path)
    assert cleanup["status"] == "removed"
    assert not generated_dir.exists()


def test_recursive_scan_and_stable_sheet_positions(tmp_path: Path) -> None:
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    for index in range(5):
        target = nested if index == 4 else source
        _write_image(target / f"{index}.png", (index * 30, 20, 40, 255))

    flat = contact_sheets.build_contact_sheets(
        source,
        grid_size=2,
    )
    flat_manifest = json.loads(Path(flat["manifestPath"]).read_text(encoding="utf-8"))
    assert flat_manifest["acceptedImages"] == 4
    contact_sheets.cleanup_manifest(flat["manifestPath"])

    recursive = contact_sheets.build_contact_sheets(
        source,
        recursive=True,
        grid_size=2,
    )
    recursive_manifest = json.loads(
        Path(recursive["manifestPath"]).read_text(encoding="utf-8")
    )
    assert recursive_manifest["acceptedImages"] == 5
    assert recursive_manifest["sheets"][1]["imageIds"] == ["IMG_00005"]
    assert recursive_manifest["images"][-1]["relativePath"] == "nested/4.png"
    contact_sheets.cleanup_manifest(recursive["manifestPath"])


def test_all_corrupt_images_still_produce_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad.png").write_bytes(b"bad")
    (source / "empty.avif").write_bytes(b"")

    result = contact_sheets.build_contact_sheets(source)
    manifest = json.loads(Path(result["manifestPath"]).read_text(encoding="utf-8"))

    assert result["status"] == "no_decodable_images"
    assert manifest["acceptedImages"] == 0
    assert manifest["invalidImageCount"] == 2
    assert manifest["sheets"] == []
    contact_sheets.cleanup_manifest(result["manifestPath"])


def test_cleanup_rejects_tampered_marker(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_image(source / "one.png", (10, 20, 30, 255))
    result = contact_sheets.build_contact_sheets(source)
    manifest_path = Path(result["manifestPath"])
    marker_path = manifest_path.parent / contact_sheets.MARKER_NAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    original_session_id = marker["sessionId"]
    marker["sessionId"] = "tampered"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    try:
        with pytest.raises(contact_sheets.ReviewError, match="session"):
            contact_sheets.cleanup_manifest(manifest_path)
        assert manifest_path.parent.exists()
    finally:
        marker["sessionId"] = original_session_id
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        contact_sheets.cleanup_manifest(manifest_path)


def test_cleanup_rejects_target_outside_system_temp(tmp_path: Path) -> None:
    target = tmp_path / f"{contact_sheets.OUTPUT_PREFIX}forged"
    target.mkdir()
    session_id = "forged-session"
    marker = {
        "schema": contact_sheets.MARKER_SCHEMA,
        "sessionId": session_id,
        "generatedDir": str(target),
    }
    manifest = {
        "schema": contact_sheets.MANIFEST_SCHEMA,
        "sessionId": session_id,
        "sourceDir": str(tmp_path / "source"),
        "generatedDir": str(target),
        "sheets": [],
    }
    (target / contact_sheets.MARKER_NAME).write_text(
        json.dumps(marker),
        encoding="utf-8",
    )
    manifest_path = target / contact_sheets.MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(contact_sheets.ReviewError, match="direct child"):
        contact_sheets.cleanup_manifest(manifest_path)
    assert manifest_path.is_file()


def test_cleanup_rejects_unexpected_entries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_image(source / "one.png", (10, 20, 30, 255))
    result = contact_sheets.build_contact_sheets(source)
    manifest_path = Path(result["manifestPath"])
    unexpected = manifest_path.parent / "keep.txt"
    unexpected.write_text("must not be deleted", encoding="utf-8")

    try:
        with pytest.raises(contact_sheets.ReviewError, match="Unexpected entry"):
            contact_sheets.cleanup_manifest(manifest_path)
        assert unexpected.read_text(encoding="utf-8") == "must not be deleted"
    finally:
        unexpected.unlink()
        contact_sheets.cleanup_manifest(manifest_path)


def test_windows_reparse_attribute_is_detected() -> None:
    fake_path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_file_attributes=0x0400)
    )
    assert contact_sheets._is_reparse_point(fake_path)


def test_cli_emits_json_and_round_trips(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for index in range(4):
        _write_image(source / f"{index}.png", (index * 40, 30, 20, 255))

    build = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "build",
            "--source",
            str(source),
            "--grid-size",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(build.stdout)
    manifest_path = Path(payload["manifestPath"])
    assert payload["acceptedImages"] == 4
    assert manifest_path.is_file()

    cleanup = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "cleanup",
            "--manifest",
            str(manifest_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(cleanup.stdout)["status"] == "removed"
    assert not manifest_path.parent.exists()
