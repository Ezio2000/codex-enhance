# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = []
# ///
"""Resolve read-only Git review scopes into a stable JSON manifest.

Successful output uses ``code-enhance/review-scope/v1`` and always contains
``status``, ``mode``, repository/path identity, ``basis``, complete
``included_files``/``excluded_files``/``uncovered_files`` arrays, matching
``counts``, ``empty``, ``exclusion_rules``, ``uncovered_rules``, and
``diagnostics``. Historical mode additionally contains independent
``comparisons`` with the same coverage arrays and counts for every interval.
Failures use the same schema with ``status: error`` and an ``error`` object
containing stable ``code`` and human-readable ``message`` fields.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

CLI_VERSION = "0.1.0"
SCHEMA = "code-enhance/review-scope/v1"

DEPENDENCY_DIRECTORIES = frozenset(
    {
        ".bundle",
        ".gradle",
        ".pnpm-store",
        ".venv",
        "bower_components",
        "carthage",
        "deps",
        "external",
        "externals",
        "node_modules",
        "pods",
        "site-packages",
        "third-party",
        "third_party",
        "vendor",
        "venv",
    }
)
GENERATED_DIRECTORIES = frozenset(
    {
        ".cache",
        ".coverage",
        ".mypy_cache",
        ".next",
        ".nox",
        ".nuxt",
        ".parcel-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "__pycache__",
        "artifacts",
        "build",
        "coverage",
        "deriveddata",
        "dist",
        "generated",
        "gen",
        "obj",
        "out",
        "target",
    }
)
LOCK_FILE_NAMES = frozenset(
    {
        "bun.lock",
        "bun.lockb",
        "cargo.lock",
        "composer.lock",
        "flake.lock",
        "gemfile.lock",
        "go.sum",
        "package-lock.json",
        "packages.lock.json",
        "pipfile.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pubspec.lock",
        "uv.lock",
        "yarn.lock",
    }
)
BINARY_EXTENSIONS = frozenset(
    {
        ".7z",
        ".a",
        ".avi",
        ".avif",
        ".bin",
        ".bmp",
        ".class",
        ".db",
        ".dll",
        ".dmg",
        ".doc",
        ".docx",
        ".dylib",
        ".eot",
        ".exe",
        ".gif",
        ".gz",
        ".heic",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".mov",
        ".mp3",
        ".mp4",
        ".o",
        ".otf",
        ".pdf",
        ".png",
        ".pyc",
        ".pyd",
        ".so",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tif",
        ".tiff",
        ".ttf",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xls",
        ".xlsx",
        ".xz",
        ".zip",
    }
)
CODE_EXTENSIONS = frozenset(
    {
        ".asm",
        ".astro",
        ".bash",
        ".bat",
        ".c",
        ".cc",
        ".cfg",
        ".cjs",
        ".clj",
        ".cljc",
        ".cljs",
        ".cmake",
        ".cmd",
        ".conf",
        ".cpp",
        ".cs",
        ".css",
        ".cxx",
        ".dart",
        ".eex",
        ".edn",
        ".ejs",
        ".elm",
        ".erl",
        ".ex",
        ".exs",
        ".fish",
        ".fs",
        ".fsi",
        ".fsx",
        ".gemspec",
        ".go",
        ".gradle",
        ".graphql",
        ".gql",
        ".groovy",
        ".h",
        ".hbs",
        ".hh",
        ".hpp",
        ".hrl",
        ".hs",
        ".htm",
        ".html",
        ".hxx",
        ".ini",
        ".ipynb",
        ".java",
        ".jinja",
        ".jinja2",
        ".js",
        ".json",
        ".json5",
        ".jsonc",
        ".jsx",
        ".kt",
        ".kts",
        ".less",
        ".lhs",
        ".lua",
        ".m",
        ".mdc",
        ".mdx",
        ".mjs",
        ".mm",
        ".ml",
        ".mli",
        ".move",
        ".nix",
        ".php",
        ".pl",
        ".plist",
        ".pm",
        ".properties",
        ".proto",
        ".ps1",
        ".py",
        ".pyi",
        ".pyx",
        ".r",
        ".rb",
        ".rs",
        ".sass",
        ".scala",
        ".scss",
        ".sh",
        ".sol",
        ".sql",
        ".svelte",
        ".swift",
        ".tf",
        ".tfvars",
        ".toml",
        ".ts",
        ".tsx",
        ".tmpl",
        ".tpl",
        ".vb",
        ".vue",
        ".xml",
        ".yaml",
        ".yml",
        ".zig",
        ".zsh",
    }
)
CODE_FILE_NAMES = frozenset(
    {
        ".editorconfig",
        ".babelrc",
        ".dockerignore",
        ".eslintrc",
        ".gitattributes",
        ".gitignore",
        ".npmrc",
        ".nvmrc",
        ".prettierrc",
        ".python-version",
        ".ruby-version",
        ".tool-versions",
        ".yarnrc",
        "agents.md",
        "build",
        "claude.md",
        "cmakelists.txt",
        "copilot-instructions.md",
        "constraints.txt",
        "dockerfile",
        "gemfile",
        "jenkinsfile",
        "justfile",
        "makefile",
        "procfile",
        "rakefile",
        "requirements.txt",
        "skill.md",
        "workspace",
    }
)
PROMPT_MARKDOWN_DIRECTORIES = frozenset(
    {
        ".claude",
        ".codex",
        ".cursor",
        "agents",
        "commands",
        "instructions",
        "prompts",
        "references",
        "rules",
        "skills",
    }
)
KNOWN_NON_CODE_EXTENSIONS = frozenset(
    {
        ".adoc",
        ".csv",
        ".license",
        ".markdown",
        ".md",
        ".rst",
        ".svg",
        ".tsv",
        ".txt",
    }
)
KNOWN_NON_CODE_NAMES = frozenset(
    {
        "authors",
        "changelog",
        "code_of_conduct",
        "codeowners",
        "contributing",
        "copying",
        "license",
        "notice",
        "readme",
        "security",
    }
)
GENERATED_NAME_PARTS = (
    ".designer.",
    ".generated.",
    ".min.css",
    ".min.js",
    ".pb.go",
    ".pb.swift",
    "_generated.",
    "_pb2.py",
)
GENERATED_MARKERS = (
    b"@generated",
    b"automatically generated",
    b"code generated",
    b"generated file",
    b"<auto-generated",
    b"this file is generated",
)
GENERATED_COMMENT_PREFIXES = (
    b"#",
    b"//",
    b"/*",
    b"*",
    b"<!--",
    b";",
    b"--",
    b"rem ",
)
EXCLUSION_RULES = (
    {
        "reason": "dependency_directory",
        "description": "Third-party dependency and vendored source directories.",
    },
    {
        "reason": "generated_or_build_directory",
        "description": "Generated code, build output, coverage, and cache directories.",
    },
    {
        "reason": "generated_file",
        "description": (
            "Generated/minified filename patterns or generated-file markers."
        ),
    },
    {
        "reason": "lock_file",
        "description": "Dependency lock and checksum files.",
    },
    {
        "reason": "binary_extension",
        "description": "Known binary, media, archive, font, and office formats.",
    },
    {
        "reason": "binary_content",
        "description": "Files whose sampled content contains NUL bytes.",
    },
    {
        "reason": "non_code_file",
        "description": (
            "First-party text that is not source or executable configuration."
        ),
    },
    {
        "reason": "symlink",
        "description": "Links are not followed during scope discovery.",
    },
    {
        "reason": "missing_from_worktree",
        "description": "Tracked entries that are absent from the current worktree.",
    },
)
UNCOVERED_RULES = (
    {
        "reason": "unrecognized_text_type",
        "description": (
            "A first-party text file could be source, but its type cannot be "
            "classified safely."
        ),
    },
    {
        "reason": "unreadable_file",
        "description": "A current first-party path could not be read safely.",
    },
    {
        "reason": "historical_content_unavailable",
        "description": "A required committed blob could not be read.",
    },
)
UNCOVERED_REASONS = frozenset(rule["reason"] for rule in UNCOVERED_RULES)


class ScopeError(Exception):
    """A stable, machine-readable scope error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class JsonArgumentParser(argparse.ArgumentParser):
    """Report argument failures through the same JSON error contract."""

    def error(self, message: str) -> None:
        raise ScopeError("invalid_arguments", message)


@dataclass
class Change:
    """A file change merged across one or more read-only Git observations."""

    path: str
    change_types: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    old_paths: set[str] = field(default_factory=set)

    def merge(
        self,
        *,
        change_type: str,
        source: str,
        old_path: str | None = None,
    ) -> None:
        self.change_types.add(change_type)
        self.sources.add(source)
        if old_path is not None and old_path != self.path:
            self.old_paths.add(old_path)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "change_types": sorted(self.change_types),
            "sources": sorted(self.sources),
        }
        if self.old_paths:
            payload["old_paths"] = sorted(self.old_paths)
        return payload


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _git(
    repository: Path,
    *arguments: str,
    check: bool = True,
    timeout: float = 20,
) -> bytes:
    environment = _git_environment()
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(repository), *arguments],
            capture_output=True,
            check=False,
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise ScopeError("git_not_found", "Git is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScopeError(
            "git_timeout", f"Git command timed out: git {' '.join(arguments)}"
        ) from exc

    if check and result.returncode != 0:
        detail = _decode(result.stderr).strip() or "Git command failed."
        raise ScopeError("git_command_failed", detail)
    return result.stdout


def _repository_root(anchor: str | Path) -> Path:
    candidate = Path(anchor).expanduser()
    try:
        candidate = candidate.resolve(strict=True)
    except OSError as exc:
        raise ScopeError(
            "repository_path_not_found", f"Cannot resolve repository path: {anchor}"
        ) from exc
    if candidate.is_file():
        candidate = candidate.parent
    output = _git(candidate, "rev-parse", "--show-toplevel", check=False)
    if not output:
        raise ScopeError("not_a_git_repository", f"Not a Git repository: {candidate}")
    root = Path(_decode(output).strip()).resolve()
    if not (root / ".git").exists():
        raise ScopeError("not_a_git_repository", f"Not a Git worktree: {candidate}")
    return root


def _scope_path(
    root: Path,
    requested: str | None,
    *,
    must_exist: bool,
) -> tuple[Path, str]:
    raw = Path(requested).expanduser() if requested else root
    candidate = raw if raw.is_absolute() else root / raw
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise ScopeError(
            "scope_path_not_found", f"Cannot resolve review path: {candidate}"
        ) from exc
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ScopeError(
            "path_outside_repository",
            f"Review path is outside the repository: {resolved}",
        ) from exc
    if must_exist and not (resolved.is_file() or resolved.is_dir()):
        raise ScopeError(
            "scope_path_not_found", f"Review path does not exist: {resolved}"
        )
    relative_text = relative.as_posix() or "."
    return resolved, relative_text


def _literal_pathspec(relative_path: str) -> str:
    if relative_path == ".":
        return "."
    return f":(literal){relative_path}"


def _path_exists_at_ref(root: Path, ref: str, relative_path: str) -> bool:
    if relative_path == ".":
        return True
    object_name = f"{ref}:{relative_path}"
    return bool(_git(root, "cat-file", "-t", object_name, check=False).strip())


def _validate_path_in_refs(
    root: Path,
    requested_path: Path,
    relative_path: str,
    refs: Sequence[str],
) -> None:
    if requested_path.exists() or requested_path.is_symlink():
        return
    if any(_path_exists_at_ref(root, ref, relative_path) for ref in refs if ref):
        return
    raise ScopeError(
        "scope_path_not_found",
        f"Review path does not exist in the worktree or requested history: "
        f"{requested_path}",
    )


def _split_nul(output: bytes) -> list[str]:
    values = output.split(b"\0")
    if values and not values[-1]:
        values.pop()
    return [_decode(value) for value in values]


def _ls_files(root: Path, relative_path: str, *options: str) -> list[str]:
    output = _git(
        root,
        "ls-files",
        "-z",
        *options,
        "--",
        _literal_pathspec(relative_path),
    )
    return _split_nul(output)


def _status_name(code: str) -> str:
    return {
        "A": "added",
        "C": "copied",
        "D": "deleted",
        "M": "modified",
        "R": "renamed",
        "T": "type_changed",
        "U": "unmerged",
        "X": "unknown",
    }.get(code[:1], "unknown")


def _parse_name_status(
    output: bytes, source: str
) -> list[tuple[str, str, str, str | None]]:
    tokens = _split_nul(output)
    changes: list[tuple[str, str, str, str | None]] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if not status:
            continue
        if status[:1] in {"R", "C"}:
            if index + 1 >= len(tokens):
                raise ScopeError(
                    "unexpected_git_output",
                    f"Incomplete rename/copy record from {source}.",
                )
            old_path, path = tokens[index], tokens[index + 1]
            index += 2
            changes.append((path, _status_name(status), source, old_path))
        else:
            if index >= len(tokens):
                raise ScopeError(
                    "unexpected_git_output",
                    f"Incomplete name-status record from {source}.",
                )
            path = tokens[index]
            index += 1
            changes.append((path, _status_name(status), source, None))
    return changes


def _diff_changes(
    root: Path,
    arguments: Sequence[str],
    *,
    source: str,
    relative_path: str,
) -> list[tuple[str, str, str, str | None]]:
    output = _git(
        root,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--name-status",
        "-z",
        "-M",
        *arguments,
        "--",
        _literal_pathspec(relative_path),
    )
    return _parse_name_status(output, source)


def _is_code_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.casefold()
    directory_parts = {part.casefold() for part in pure.parts[:-1]}
    if name in CODE_FILE_NAMES or pure.suffix.casefold() in CODE_EXTENSIONS:
        return True
    return pure.suffix.casefold() in {".md", ".markdown"} and bool(
        directory_parts & PROMPT_MARKDOWN_DIRECTORIES
    )


def _is_known_non_code_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.casefold()
    stem = pure.stem.casefold()
    return (
        pure.suffix.casefold() in KNOWN_NON_CODE_EXTENSIONS
        or name in KNOWN_NON_CODE_NAMES
        or stem in KNOWN_NON_CODE_NAMES
    )


def _path_exclusion(path: str) -> str | None:
    pure = PurePosixPath(path)
    directory_parts = {part.casefold() for part in pure.parts[:-1]}
    if directory_parts & DEPENDENCY_DIRECTORIES:
        return "dependency_directory"
    if directory_parts & GENERATED_DIRECTORIES:
        return "generated_or_build_directory"

    name = pure.name.casefold()
    if name in LOCK_FILE_NAMES or name.endswith(".lock"):
        return "lock_file"
    if any(fragment in name for fragment in GENERATED_NAME_PARTS):
        return "generated_file"
    if pure.suffix.casefold() in BINARY_EXTENSIONS:
        return "binary_extension"
    if not _is_code_path(path):
        if _is_known_non_code_path(path):
            return "non_code_file"
        return "unrecognized_text_type"
    return None


def _has_generated_header(header: bytes) -> bool:
    logical_lines = 0
    for raw_line in header.lstrip(b"\xef\xbb\xbf").splitlines():
        stripped = raw_line.strip().lower()
        if not stripped:
            continue
        logical_lines += 1
        if logical_lines > 12:
            break
        if stripped.startswith(GENERATED_COMMENT_PREFIXES) and any(
            marker in stripped for marker in GENERATED_MARKERS
        ):
            return True
    return False


def _inspect_current_content(root: Path, path: str) -> tuple[str | None, bool]:
    target = root.joinpath(*PurePosixPath(path).parts)
    if not target.exists():
        return None, False
    if target.is_symlink():
        return "symlink", False
    if not target.is_file():
        return "missing_from_worktree", False
    header = bytearray()
    try:
        with target.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                if len(header) < 16_384:
                    header.extend(chunk[: 16_384 - len(header)])
                if b"\0" in chunk:
                    return "binary_content", False
    except OSError:
        return "unreadable_file", False
    header_bytes = bytes(header)
    if _has_generated_header(header_bytes):
        return "generated_file", False
    return None, header_bytes.startswith(b"#!")


def _classify_current(root: Path, path: str) -> str | None:
    path_reason = _path_exclusion(path)
    if path_reason not in {None, "non_code_file", "unrecognized_text_type"}:
        return path_reason
    content_reason, has_shebang = _inspect_current_content(root, path)
    if content_reason is not None:
        return content_reason
    if has_shebang:
        return None
    return path_reason


def _inspect_git_blob(
    root: Path,
    object_name: str,
) -> tuple[bool, str | None, bool]:
    if not _git(root, "cat-file", "-s", object_name, check=False).strip():
        return False, None, False

    try:
        process = subprocess.Popen(
            ["git", "-C", os.fspath(root), "cat-file", "blob", object_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_git_environment(),
        )
    except OSError as exc:
        raise ScopeError(
            "git_command_failed", f"Cannot inspect historical object: {object_name}"
        ) from exc

    if process.stdout is None:
        process.kill()
        process.wait()
        raise ScopeError(
            "git_command_failed", f"Cannot read historical object: {object_name}"
        )

    header = bytearray()
    binary = False
    try:
        while chunk := process.stdout.read(64 * 1024):
            if len(header) < 16_384:
                header.extend(chunk[: 16_384 - len(header)])
            if b"\0" in chunk:
                binary = True
    finally:
        process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        return False, None, False
    if binary:
        return True, "binary_content", False

    header_bytes = bytes(header)
    if _has_generated_header(header_bytes):
        return True, "generated_file", False
    return True, None, header_bytes.startswith(b"#!")


def _inspect_historical_content(
    root: Path,
    path: str,
    refs: Sequence[str],
    *,
    include_index: bool = False,
) -> tuple[str | None, bool]:
    if include_index:
        found, reason, has_shebang = _inspect_git_blob(root, f":{path}")
        if found:
            return reason, has_shebang
    for ref in refs:
        found, reason, has_shebang = _inspect_git_blob(root, f"{ref}:{path}")
        if found:
            return reason, has_shebang
    return "historical_content_unavailable", False


def _classify_historical(
    root: Path,
    path: str,
    refs: Sequence[str],
    *,
    include_index: bool = False,
) -> str | None:
    path_reason = _path_exclusion(path)
    if path_reason not in {None, "non_code_file", "unrecognized_text_type"}:
        return path_reason
    content_reason, has_shebang = _inspect_historical_content(
        root,
        path,
        refs,
        include_index=include_index,
    )
    if content_reason is not None:
        return content_reason
    if has_shebang:
        return None
    return path_reason


def _empty_manifest(
    *,
    mode: str,
    root: Path,
    requested_path: Path,
    relative_path: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "ok",
        "mode": mode,
        "repository_root": os.fspath(root),
        "requested_path": os.fspath(requested_path),
        "scope_path": relative_path,
        "basis": {},
        "included_files": [],
        "excluded_files": [],
        "uncovered_files": [],
        "counts": {"included": 0, "excluded": 0, "uncovered": 0},
        "empty": True,
        "exclusion_rules": list(EXCLUSION_RULES),
        "uncovered_rules": list(UNCOVERED_RULES),
        "diagnostics": [],
    }


def _finish_manifest(
    manifest: dict[str, Any],
    *,
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    uncovered: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    uncovered = uncovered or []
    manifest["included_files"] = included
    manifest["excluded_files"] = excluded
    manifest["uncovered_files"] = uncovered
    manifest["counts"] = {
        "included": len(included),
        "excluded": len(excluded),
        "uncovered": len(uncovered),
    }
    manifest["empty"] = not included
    return manifest


def repository_scope(repository: str | Path, path: str | None = None) -> dict[str, Any]:
    """Return all current tracked and non-ignored untracked first-party code."""

    root = _repository_root(repository)
    requested_path, relative_path = _scope_path(root, path, must_exist=True)
    manifest = _empty_manifest(
        mode="repository",
        root=root,
        requested_path=requested_path,
        relative_path=relative_path,
    )
    tracked = set(_ls_files(root, relative_path, "--cached"))
    untracked = set(_ls_files(root, relative_path, "--others", "--exclude-standard"))
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []

    for file_path in sorted(
        tracked | untracked, key=lambda item: (item.casefold(), item)
    ):
        source = "tracked" if file_path in tracked else "untracked"
        target = root.joinpath(*PurePosixPath(file_path).parts)
        if source == "tracked" and not target.exists() and not target.is_symlink():
            reason = "missing_from_worktree"
        else:
            reason = _classify_current(root, file_path)
        item = {"path": file_path, "source": source}
        if reason is None:
            included.append(item)
        elif reason in UNCOVERED_REASONS:
            uncovered.append({**item, "reason": reason})
        else:
            excluded.append({**item, "reason": reason})

    manifest["basis"] = {
        "tracked_files": len(tracked),
        "non_ignored_untracked_files": len(untracked),
        "ignored_files_enumerated": False,
    }
    return _finish_manifest(
        manifest,
        included=included,
        excluded=excluded,
        uncovered=uncovered,
    )


def _verify_ref(root: Path, ref: str) -> str:
    output = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{ref}^{{commit}}",
        check=False,
    )
    commit = _decode(output).strip()
    if not commit:
        raise ScopeError("invalid_ref", f"Ref does not resolve to a commit: {ref}")
    return commit


def _head_commit(root: Path) -> str | None:
    output = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD^{commit}",
        check=False,
    )
    return _decode(output).strip() or None


def _resolve_branch_candidate(root: Path, name: str) -> tuple[str, str] | None:
    normalized = name.removeprefix("refs/heads/")
    candidates: list[str] = []
    if name.startswith("refs/"):
        candidates.append(name)
    if name.startswith("origin/"):
        candidates.extend([name, f"refs/remotes/{name}"])
    else:
        candidates.extend(
            [
                f"refs/remotes/origin/{normalized}",
                f"origin/{normalized}",
                f"refs/heads/{normalized}",
                normalized,
            ]
        )
    for candidate in dict.fromkeys(candidates):
        output = _git(
            root,
            "rev-parse",
            "--verify",
            "--quiet",
            f"{candidate}^{{commit}}",
            check=False,
        )
        commit = _decode(output).strip()
        if commit:
            return candidate, commit
    return None


def _pr_base_from_environment(root: Path) -> tuple[str, str] | None:
    for variable in (
        "GITHUB_BASE_REF",
        "CI_MERGE_REQUEST_TARGET_BRANCH_NAME",
        "SYSTEM_PULLREQUEST_TARGETBRANCH",
        "BUILDKITE_PULL_REQUEST_BASE_BRANCH",
        "CHANGE_TARGET",
    ):
        value = os.environ.get(variable, "").strip()
        if not value:
            continue
        resolved = _resolve_branch_candidate(root, value)
        if resolved is not None:
            return resolved
    return None


def _pr_base_from_gh(root: Path) -> tuple[str, str] | None:
    executable = shutil.which("gh")
    if executable is None:
        return None
    environment = os.environ.copy()
    environment.update({"GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0"})
    try:
        result = subprocess.run(
            [
                executable,
                "pr",
                "view",
                "--json",
                "baseRefName",
                "--jq",
                ".baseRefName",
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    name = _decode(result.stdout).strip()
    return _resolve_branch_candidate(root, name) if name else None


def _remote_default(root: Path) -> tuple[str, str] | None:
    branch_remote = _decode(
        _git(
            root,
            "config",
            "--get",
            f"branch.{_current_branch(root)}.remote",
            check=False,
        )
    ).strip()
    remotes = [
        line for line in _decode(_git(root, "remote", check=False)).splitlines() if line
    ]
    ordered = [
        remote
        for remote in dict.fromkeys([branch_remote, "origin", *sorted(remotes)])
        if remote and remote != "."
    ]
    for remote in ordered:
        symbolic = _decode(
            _git(
                root,
                "symbolic-ref",
                "--quiet",
                "--short",
                f"refs/remotes/{remote}/HEAD",
                check=False,
            )
        ).strip()
        if symbolic:
            resolved = _resolve_branch_candidate(root, symbolic)
            if resolved is not None:
                return resolved
    return None


def _current_branch(root: Path) -> str:
    return _decode(
        _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    ).strip()


def _upstream(root: Path) -> tuple[str, str] | None:
    name = _decode(
        _git(
            root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
            check=False,
        )
    ).strip()
    if not name:
        return None
    output = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{name}^{{commit}}",
        check=False,
    )
    commit = _decode(output).strip()
    return (name, commit) if commit else None


def _resolve_base(
    root: Path,
    *,
    explicit_base: str | None,
    explicit_pr_base: str | None,
) -> tuple[str | None, str | None, str]:
    if explicit_base:
        return explicit_base, _verify_ref(root, explicit_base), "explicit"
    if explicit_pr_base:
        resolved = _resolve_branch_candidate(root, explicit_pr_base)
        if resolved is None:
            raise ScopeError(
                "invalid_ref",
                f"PR base does not resolve to a local commit: {explicit_pr_base}",
            )
        return resolved[0], resolved[1], "pull_request"

    pr_base = _pr_base_from_environment(root) or _pr_base_from_gh(root)
    if pr_base is not None:
        return pr_base[0], pr_base[1], "pull_request"

    remote_default = _remote_default(root)
    if remote_default is not None:
        return remote_default[0], remote_default[1], "remote_default"

    upstream = _upstream(root)
    if upstream is not None:
        return upstream[0], upstream[1], "upstream"

    parent = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD^",
        check=False,
    )
    parent_commit = _decode(parent).strip()
    if parent_commit:
        return "HEAD^", parent_commit, "head_parent"
    return None, None, "initial_repository"


def _merge_change(
    changes: dict[str, Change],
    path: str,
    change_type: str,
    source: str,
    old_path: str | None,
) -> None:
    item = changes.setdefault(path, Change(path))
    item.merge(change_type=change_type, source=source, old_path=old_path)


def development_scope(
    repository: str | Path,
    path: str | None = None,
    *,
    base: str | None = None,
    pr_base: str | None = None,
) -> dict[str, Any]:
    """Return branch, index, worktree, and untracked development changes."""

    root = _repository_root(repository)
    requested_path, relative_path = _scope_path(root, path, must_exist=False)
    manifest = _empty_manifest(
        mode="development_delta",
        root=root,
        requested_path=requested_path,
        relative_path=relative_path,
    )
    head = _head_commit(root)
    base_ref, base_commit, base_source = _resolve_base(
        root,
        explicit_base=base,
        explicit_pr_base=pr_base,
    )
    if path is not None:
        _validate_path_in_refs(
            root,
            requested_path,
            relative_path,
            tuple(ref for ref in (head, base_commit) if isinstance(ref, str) and ref),
        )
    changes: dict[str, Change] = {}

    if head is not None and base_ref is not None:
        for item in _diff_changes(
            root,
            [f"{base_ref}...HEAD"],
            source="branch_commits",
            relative_path=relative_path,
        ):
            _merge_change(changes, *item)
    elif base_ref is None:
        snapshot = repository_scope(root, relative_path)
        for item in snapshot["included_files"]:
            _merge_change(changes, item["path"], "added", "initial_repository", None)
        for item in snapshot["excluded_files"]:
            _merge_change(changes, item["path"], "added", "initial_repository", None)
        for item in snapshot["uncovered_files"]:
            _merge_change(changes, item["path"], "added", "initial_repository", None)

    for item in _diff_changes(
        root,
        ["--cached"],
        source="staged",
        relative_path=relative_path,
    ):
        _merge_change(changes, *item)
    for item in _diff_changes(
        root,
        [],
        source="unstaged",
        relative_path=relative_path,
    ):
        _merge_change(changes, *item)
    for file_path in _ls_files(root, relative_path, "--others", "--exclude-standard"):
        _merge_change(changes, file_path, "added", "untracked", None)

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    historical_refs = tuple(
        ref for ref in (head, base_ref) if isinstance(ref, str) and ref
    )

    def record(payload: dict[str, Any], reason: str | None) -> None:
        if reason is None:
            included.append(payload)
        elif reason in UNCOVERED_REASONS:
            uncovered.append({**payload, "reason": reason})
        else:
            excluded.append({**payload, "reason": reason})

    for file_path in sorted(changes, key=lambda item: (item.casefold(), item)):
        change = changes[file_path]
        payload = change.as_dict()
        if "deleted" in change.change_types:
            reason = _classify_historical(
                root,
                file_path,
                historical_refs,
                include_index="staged" in change.sources,
            )
        else:
            reason = _classify_current(root, file_path)
        record(payload, reason)

        if "renamed" not in change.change_types:
            continue
        for old_path in sorted(change.old_paths):
            old_reason = _classify_historical(root, old_path, historical_refs)
            if reason is None and old_reason is None:
                continue
            old_payload = {
                "path": old_path,
                "change_types": ["deleted"],
                "sources": sorted(change.sources),
                "renamed_to": [file_path],
            }
            if reason is not None and old_reason is None:
                record(old_payload, None)
            elif reason is None and old_reason is not None:
                record(old_payload, old_reason)

    manifest["basis"] = {
        "base_ref": base_ref,
        "base_commit": base_commit,
        "base_source": base_source,
        "head_commit": head,
        "branch": _current_branch(root) or None,
        "includes": ["branch_commits", "staged", "unstaged", "untracked"],
    }
    if not included:
        manifest["diagnostics"].append("No reviewable development changes were found.")
    return _finish_manifest(
        manifest,
        included=included,
        excluded=excluded,
        uncovered=uncovered,
    )


def _comparison_scope(
    root: Path,
    *,
    left_ref: str,
    right_ref: str,
    left_commit: str,
    right_commit: str,
    relative_path: str,
    comparison_id: str,
) -> dict[str, Any]:
    changes: dict[str, Change] = {}
    for item in _diff_changes(
        root,
        [f"{left_ref}..{right_ref}"],
        source=comparison_id,
        relative_path=relative_path,
    ):
        _merge_change(changes, *item)

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []

    def record(payload: dict[str, Any], reason: str | None) -> None:
        if reason is None:
            included.append(payload)
        elif reason in UNCOVERED_REASONS:
            uncovered.append({**payload, "reason": reason})
        else:
            excluded.append({**payload, "reason": reason})

    for path in sorted(changes, key=lambda item: (item.casefold(), item)):
        change = changes[path]
        payload = change.as_dict()
        reason = _classify_historical(root, path, (right_ref, left_ref))
        record(payload, reason)

        if "renamed" not in change.change_types:
            continue
        for old_path in sorted(change.old_paths):
            old_reason = _classify_historical(root, old_path, (left_ref,))
            if reason is None and old_reason is None:
                continue
            old_payload = {
                "path": old_path,
                "change_types": ["deleted"],
                "sources": sorted(change.sources),
                "renamed_to": [path],
            }
            if reason is not None and old_reason is None:
                record(old_payload, None)
            elif reason is None and old_reason is not None:
                record(old_payload, old_reason)
    return {
        "id": comparison_id,
        "from_ref": left_ref,
        "from_commit": left_commit,
        "to_ref": right_ref,
        "to_commit": right_commit,
        "included_files": included,
        "excluded_files": excluded,
        "uncovered_files": uncovered,
        "counts": {
            "included": len(included),
            "excluded": len(excluded),
            "uncovered": len(uncovered),
        },
        "empty": not included,
    }


def version_scope(
    repository: str | Path,
    refs: Sequence[str],
    path: str | None = None,
    *,
    explicit_comparisons: Sequence[Sequence[str]] = (),
) -> dict[str, Any]:
    """Return independent historical comparisons without worktree changes."""

    root = _repository_root(repository)
    requested_path, relative_path = _scope_path(root, path, must_exist=False)
    manifest = _empty_manifest(
        mode="version_comparison",
        root=root,
        requested_path=requested_path,
        relative_path=relative_path,
    )

    pairs: list[tuple[str, str]]
    relation: str
    if explicit_comparisons:
        pairs = []
        for comparison in explicit_comparisons:
            if len(comparison) != 2:
                raise ScopeError(
                    "ambiguous_comparison",
                    "Every explicit comparison must contain exactly two refs.",
                )
            pairs.append((comparison[0], comparison[1]))
        relation = "explicit"
    else:
        if len(refs) < 2:
            raise ScopeError(
                "ambiguous_comparison",
                "Historical review needs at least two refs or an explicit comparison.",
            )
        pairs = list(zip(refs, refs[1:], strict=False))
        relation = "adjacent"

    mentioned_refs = [ref for pair in pairs for ref in pair]
    mentioned_refs.extend(refs)
    commits = {ref: _verify_ref(root, ref) for ref in dict.fromkeys(mentioned_refs)}
    if path is not None:
        _validate_path_in_refs(
            root,
            requested_path,
            relative_path,
            tuple(commits.values()),
        )

    comparisons = [
        _comparison_scope(
            root,
            left_ref=left,
            right_ref=right,
            left_commit=commits[left],
            right_commit=commits[right],
            relative_path=relative_path,
            comparison_id=f"C{index:03d}",
        )
        for index, (left, right) in enumerate(pairs, start=1)
    ]

    union_included: dict[str, dict[str, Any]] = {}
    union_excluded: dict[tuple[str, str], dict[str, Any]] = {}
    union_uncovered: dict[tuple[str, str], dict[str, Any]] = {}
    for comparison in comparisons:
        for item in comparison["included_files"]:
            entry = union_included.setdefault(
                item["path"],
                {"path": item["path"], "comparison_ids": []},
            )
            entry["comparison_ids"].append(comparison["id"])
        for item in comparison["uncovered_files"]:
            key = (item["path"], item["reason"])
            entry = union_uncovered.setdefault(
                key,
                {
                    "path": item["path"],
                    "reason": item["reason"],
                    "comparison_ids": [],
                },
            )
            entry["comparison_ids"].append(comparison["id"])
        for item in comparison["excluded_files"]:
            key = (item["path"], item["reason"])
            entry = union_excluded.setdefault(
                key,
                {
                    "path": item["path"],
                    "reason": item["reason"],
                    "comparison_ids": [],
                },
            )
            entry["comparison_ids"].append(comparison["id"])

    manifest["basis"] = {
        "relation": relation,
        "refs": [{"ref": ref, "commit": commit} for ref, commit in commits.items()],
        "worktree_changes_included": False,
    }
    manifest["comparisons"] = comparisons
    if all(comparison["empty"] for comparison in comparisons):
        manifest["diagnostics"].append(
            "No reviewable historical changes were found in the requested comparisons."
        )
    return _finish_manifest(
        manifest,
        included=list(union_included.values()),
        excluded=list(union_excluded.values()),
        uncovered=list(union_uncovered.values()),
    )


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=CLI_VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    repository = subparsers.add_parser("repo")
    repository.add_argument("--repository", default=".")
    repository.add_argument("--path")

    latest = subparsers.add_parser("latest")
    latest.add_argument("--repository", default=".")
    latest.add_argument("--path")
    latest.add_argument("--base")
    latest.add_argument("--pr-base")

    versions = subparsers.add_parser("versions")
    versions.add_argument("refs", nargs="*")
    versions.add_argument("--repository", default=".")
    versions.add_argument("--path")
    versions.add_argument(
        "--compare",
        nargs=2,
        action="append",
        default=[],
        metavar=("FROM", "TO"),
    )
    return parser


def _run(arguments: Sequence[str]) -> dict[str, Any]:
    parsed = _parser().parse_args(arguments)
    if parsed.command == "repo":
        return repository_scope(parsed.repository, parsed.path)
    if parsed.command == "latest":
        return development_scope(
            parsed.repository,
            parsed.path,
            base=parsed.base,
            pr_base=parsed.pr_base,
        )
    if parsed.command == "versions":
        return version_scope(
            parsed.repository,
            parsed.refs,
            parsed.path,
            explicit_comparisons=parsed.compare,
        )
    raise ScopeError("invalid_arguments", f"Unsupported command: {parsed.command}")


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        payload = _run(sys.argv[1:] if arguments is None else arguments)
    except ScopeError as exc:
        payload = {
            "schema": SCHEMA,
            "status": "error",
            "error": {"code": exc.code, "message": str(exc)},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
