from __future__ import annotations

from pathlib import Path

import pytest
from model_enhance_mcp.errors import InputError
from model_enhance_mcp.files import read_repository_file


def test_rejects_paths_outside_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(InputError, match="outside"):
        read_repository_file(root, str(outside))


def test_rejects_symlinks_and_sensitive_files(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "target.txt"
    target.write_text("safe", encoding="utf-8")
    link = root / "link.txt"
    link.symlink_to(target)
    with pytest.raises(InputError, match="symlink"):
        read_repository_file(root, "link.txt")

    secret = root / ".env.production"
    secret.write_text("TOKEN=value", encoding="utf-8")
    with pytest.raises(InputError, match="sensitive"):
        read_repository_file(root, secret.name)


def test_rejects_non_utf8_and_private_keys(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    binary = root / "binary.txt"
    binary.write_bytes(b"\xff\xfe")
    with pytest.raises(InputError, match="UTF-8"):
        read_repository_file(root, binary.name)

    private = root / "note.txt"
    private.write_text(
        "-----BEGIN TEST PRIVATE KEY-----\nsecret\n",
        encoding="utf-8",
    )
    with pytest.raises(InputError, match="private key"):
        read_repository_file(root, private.name)


def test_rejects_files_larger_than_one_mebibyte(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    oversized = root / "oversized.txt"
    oversized.write_bytes(b"x" * 1_048_577)
    with pytest.raises(InputError, match="1 MiB"):
        read_repository_file(root, oversized.name)
