"""Safe local text-file resolution."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .constants import MAX_FILE_BYTES
from .errors import InputError

_SENSITIVE_NAMES = frozenset(
    {
        "credentials",
        "credentials.json",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
    }
)
_SENSITIVE_SUFFIXES = frozenset(
    {".cer", ".crt", ".der", ".jks", ".key", ".p12", ".pem", ".pfx"}
)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")


@dataclass(frozen=True)
class LocalTextFile:
    relative_path: str
    absolute_path: Path
    text: str
    file_hash: str
    size: int


def resolve_repository(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    process = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise InputError(f"Not a Git repository: {candidate}")
    return Path(process.stdout.strip()).resolve()


def resolve_scope_path(root: Path, value: str | None) -> tuple[Path, str]:
    requested = (root / value).resolve() if value else root
    if requested != root and root not in requested.parents:
        raise InputError(f"Scope path is outside the repository: {requested}")
    if not requested.exists():
        raise InputError(f"Scope path does not exist: {requested}")
    relative = "." if requested == root else requested.relative_to(root).as_posix()
    return requested, relative


def read_repository_file(root: Path, value: str) -> LocalTextFile:
    candidate = Path(value).expanduser()
    unresolved = candidate if candidate.is_absolute() else root / candidate
    if unresolved.is_symlink():
        raise InputError(f"File must not be a symlink: {unresolved}")
    path = unresolved.resolve()
    if path == root or root not in path.parents:
        raise InputError(f"File is outside the repository: {path}")
    if path.is_symlink() or not path.is_file():
        raise InputError(f"File must be a regular non-symlink file: {path}")
    relative = path.relative_to(root).as_posix()
    reason = sensitive_path_reason(relative)
    if reason:
        raise InputError(f"Refusing sensitive file {relative}: {reason}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise InputError(f"File exceeds the 1 MiB limit: {relative}")
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"File is not valid UTF-8 text: {relative}") from exc
    if _PRIVATE_KEY.search(text):
        raise InputError(f"Refusing file containing a private key: {relative}")
    return LocalTextFile(
        relative_path=relative,
        absolute_path=path,
        text=text,
        file_hash=hashlib.sha256(raw).hexdigest(),
        size=size,
    )


def sensitive_path_reason(relative: str) -> str | None:
    path = Path(relative)
    lowered = [part.casefold() for part in path.parts]
    name = path.name.casefold()
    if ".ssh" in lowered:
        return "SSH credential directory"
    if name == ".env" or name.startswith(".env."):
        return "environment-secret filename"
    if name in _SENSITIVE_NAMES or name.startswith("id_rsa."):
        return "credential filename"
    if path.suffix.casefold() in _SENSITIVE_SUFFIXES:
        return "key or certificate suffix"
    return None
