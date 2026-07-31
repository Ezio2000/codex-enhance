"""Incremental SQLite semantic index without stored source text."""

from __future__ import annotations

import array
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .chunking import TextChunk, chunk_text
from .client import ArkEmbeddingClient
from .config import Settings
from .constants import (
    ARK_MODEL,
    BATCH_SIZE,
    CHUNKER_VERSION,
    EMBEDDING_DIMENSION,
    INDEX_SCHEMA_VERSION,
)
from .errors import IndexError, InputError
from .files import (
    LocalTextFile,
    read_repository_file,
    resolve_repository,
    resolve_scope_path,
    sensitive_path_reason,
)
from .schemas import (
    IndexSearchResult,
    IndexSyncResult,
    SearchMatch,
    Usage,
)
from .service import _ensure_outside_repository


@dataclass(frozen=True)
class PendingFile:
    file: LocalTextFile
    chunks: list[TextChunk]


@dataclass(frozen=True)
class EmbeddedChunk:
    path: str
    file_hash: str
    chunk: TextChunk
    vector: list[float]


def index_path(settings: Settings, root: Path) -> Path:
    identity = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:24]
    path = settings.cache_root / "index" / identity / "index.sqlite3"
    _ensure_outside_repository(path.parent, root)
    return path


async def sync_index(
    settings: Settings,
    repository: str,
    *,
    path: str | None = None,
    rebuild: bool = False,
    client: ArkEmbeddingClient | None = None,
) -> IndexSyncResult:
    root = resolve_repository(repository)
    _, scope_relative = resolve_scope_path(root, path)
    manifest = _scope_manifest(root, path)
    included_raw = manifest.get("included_files")
    if not isinstance(included_raw, list):
        raise IndexError("Scope helper returned no included_files array")
    included = _index_manifest_entries(manifest)
    selected_paths = {item["path"] for item in included}
    manifest_exclusions = [
        {
            "path": item["path"],
            "reason": str(item.get("reason", collection_name)),
        }
        for collection_name in ("excluded_files", "uncovered_files")
        for item in manifest.get(collection_name, [])
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and item["path"] not in selected_paths
    ]

    db_path = index_path(settings, root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        db_path.parent.chmod(0o700)
    connection = _connect(db_path)
    if os.name == "posix":
        db_path.chmod(0o600)
    try:
        compatible = _metadata_compatible(connection, root) and not rebuild
        old_files = (
            {
                row["path"]: row["file_hash"]
                for row in connection.execute("SELECT path, file_hash FROM files")
            }
            if compatible
            else {}
        )
        old_chunks = (
            {
                (row["path"], row["content_hash"]): (row["vector"], row["norm"])
                for row in connection.execute(
                    "SELECT path, content_hash, vector, norm FROM chunks"
                )
            }
            if compatible
            else {}
        )
        accepted: dict[str, LocalTextFile] = {}
        exclusions: list[dict[str, str]] = manifest_exclusions
        pending: list[PendingFile] = []
        unchanged = 0
        for item in included:
            relative = item.get("path") if isinstance(item, dict) else None
            if not isinstance(relative, str):
                continue
            try:
                local = read_repository_file(root, relative)
            except InputError as exc:
                exclusions.append({"path": relative, "reason": str(exc)})
                continue
            accepted[relative] = local
            if old_files.get(relative) == local.file_hash:
                unchanged += 1
                continue
            pending.append(PendingFile(file=local, chunks=chunk_text(local.text)))

        active_client = client or ArkEmbeddingClient(settings.api_key)
        raw_chunks = [
            (pending_file.file, chunk)
            for pending_file in pending
            for chunk in pending_file.chunks
            if (pending_file.file.relative_path, chunk.content_hash) not in old_chunks
        ]
        embedded: list[EmbeddedChunk] = []
        request_ids: list[str] = []
        prompt_tokens = 0
        total_tokens = 0
        prompt_known = True
        total_known = True
        for offset in range(0, len(raw_chunks), BATCH_SIZE):
            selected = raw_chunks[offset : offset + BATCH_SIZE]
            batch = await active_client.embed([chunk.text for _, chunk in selected])
            if batch.request_id:
                request_ids.append(batch.request_id)
            if batch.usage.prompt_tokens is None:
                prompt_known = False
            else:
                prompt_tokens += batch.usage.prompt_tokens
            if batch.usage.total_tokens is None:
                total_known = False
            else:
                total_tokens += batch.usage.total_tokens
            for (local, chunk), vector in zip(
                selected,
                batch.vectors,
                strict=True,
            ):
                embedded.append(
                    EmbeddedChunk(
                        path=local.relative_path,
                        file_hash=local.file_hash,
                        chunk=chunk,
                        vector=vector,
                    )
                )

        current_paths = set(accepted)
        old_scope_paths = {
            old_path
            for old_path in old_files
            if scope_relative == "."
            or old_path == scope_relative
            or old_path.startswith(f"{scope_relative.rstrip('/')}/")
        }
        removed_paths = old_scope_paths - current_paths
        with connection:
            if not compatible:
                connection.execute("DELETE FROM chunks")
                connection.execute("DELETE FROM files")
            for relative in removed_paths:
                connection.execute("DELETE FROM files WHERE path = ?", (relative,))
            for pending_file in pending:
                connection.execute(
                    "DELETE FROM files WHERE path = ?",
                    (pending_file.file.relative_path,),
                )
                connection.execute(
                    "INSERT INTO files(path, file_hash, size) VALUES (?, ?, ?)",
                    (
                        pending_file.file.relative_path,
                        pending_file.file.file_hash,
                        pending_file.file.size,
                    ),
                )
            embedded_by_chunk = {
                (
                    item.path,
                    item.chunk.start_line,
                    item.chunk.end_line,
                    item.chunk.content_hash,
                ): item.vector
                for item in embedded
            }
            for pending_file in pending:
                for chunk in pending_file.chunks:
                    path = pending_file.file.relative_path
                    vector = embedded_by_chunk.get(
                        (path, chunk.start_line, chunk.end_line, chunk.content_hash)
                    )
                    if vector is None:
                        packed, norm = old_chunks[(path, chunk.content_hash)]
                    else:
                        packed = _pack_vector(vector)
                        norm = _norm(vector)
                    _insert_chunk(
                        connection,
                        path=path,
                        file_hash=pending_file.file.file_hash,
                        chunk=chunk,
                        packed_vector=packed,
                        norm=norm,
                    )
            _write_metadata(connection, root)

        chunks_total = connection.execute(
            "SELECT COUNT(*) AS count FROM chunks"
        ).fetchone()["count"]
        files_indexed = connection.execute(
            "SELECT COUNT(*) AS count FROM files"
        ).fetchone()["count"]
        return IndexSyncResult(
            repository_root=str(root),
            scope_path=scope_relative,
            index_path=str(db_path),
            files_seen=len(included) + len(manifest_exclusions),
            files_indexed=files_indexed,
            files_unchanged=unchanged,
            files_removed=len(removed_paths),
            files_excluded=len(exclusions),
            chunks_embedded=len(embedded),
            chunks_total=chunks_total,
            request_ids=request_ids,
            usage=Usage(
                prompt_tokens=prompt_tokens if prompt_known else None,
                total_tokens=total_tokens if total_known else None,
            ),
            exclusions=exclusions[:100],
        )
    finally:
        connection.close()


async def search_index(
    settings: Settings,
    repository: str,
    query: str,
    *,
    path: str | None = None,
    top_k: int = 10,
    client: ArkEmbeddingClient | None = None,
) -> IndexSearchResult:
    if not query.strip():
        raise InputError("query must contain non-whitespace text")
    if len(query) > 20_000:
        raise InputError("query exceeds the 20,000 character limit")
    if not 1 <= top_k <= 50:
        raise InputError("top_k must be between 1 and 50")
    root = resolve_repository(repository)
    _, relative_scope = resolve_scope_path(root, path)
    db_path = index_path(settings, root)
    if not db_path.is_file():
        raise IndexError("Semantic index is missing; run sync_code_index first")
    connection = _connect(db_path)
    try:
        if not _metadata_compatible(connection, root):
            raise IndexError("Semantic index metadata is stale; rebuild the index")
        active_client = client or ArkEmbeddingClient(settings.api_key)
        batch = await active_client.embed([query])
        query_vector = batch.vectors[0]
        query_norm = _norm(query_vector)
        prefix = None if relative_scope == "." else f"{relative_scope.rstrip('/')}/%"
        rows = (
            connection.execute(
                """
                SELECT c.path, c.file_hash, c.start_line, c.end_line, c.vector, c.norm
                FROM chunks AS c
                WHERE c.path = ? OR c.path LIKE ?
                """,
                (relative_scope, prefix),
            )
            if prefix
            else connection.execute(
                """
                SELECT c.path, c.file_hash, c.start_line, c.end_line, c.vector, c.norm
                FROM chunks AS c
                """
            )
        )
        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vector = _unpack_vector(row["vector"])
            score = _dot(query_vector, vector) / (query_norm * row["norm"])
            ranked.append((max(-1.0, min(1.0, score)), row))
        ranked.sort(
            key=lambda item: (
                -item[0],
                item[1]["path"],
                item[1]["start_line"],
            )
        )

        matches: list[SearchMatch] = []
        stale = 0
        for score, row in ranked:
            if len(matches) >= top_k:
                break
            try:
                local = read_repository_file(root, row["path"])
            except InputError:
                stale += 1
                continue
            if local.file_hash != row["file_hash"]:
                stale += 1
                continue
            lines = local.text.splitlines()
            start = row["start_line"]
            end = row["end_line"]
            if start < 1 or end < start or end > len(lines):
                stale += 1
                continue
            preview = "\n".join(lines[start - 1 : end])
            if len(preview) > 2_000:
                preview = preview[:2_000] + "\n…"
            matches.append(
                SearchMatch(
                    path=row["path"],
                    start_line=start,
                    end_line=end,
                    score=score,
                    preview=preview,
                )
            )
        return IndexSearchResult(
            repository_root=str(root),
            index_path=str(db_path),
            query=query,
            matches=matches,
            stale_matches_skipped=stale,
            request_id=batch.request_id,
            usage=batch.usage,
        )
    finally:
        connection.close()


def _scope_manifest(root: Path, path: str | None) -> dict[str, Any]:
    helper = Path(__file__).resolve().parents[2] / "scripts" / "review_scope.py"
    command = [
        sys.executable,
        str(helper),
        "repo",
        "--repository",
        str(root),
    ]
    if path:
        command.extend(["--path", path])
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise IndexError("Scope helper returned invalid JSON") from exc
    if process.returncode != 0 or payload.get("status") != "ok":
        error = payload.get("error", {})
        message = error.get("message", "scope resolution failed")
        raise IndexError(str(message))
    return payload


def _index_manifest_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    included = [
        item
        for item in manifest.get("included_files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    ]
    known = {item["path"] for item in included}
    document_suffixes = {
        ".adoc",
        ".markdown",
        ".md",
        ".mdx",
        ".rst",
        ".txt",
    }
    document_names = {
        "changelog",
        "contributing",
        "license",
        "readme",
    }
    for collection_name in ("excluded_files", "uncovered_files"):
        for item in manifest.get(collection_name, []):
            if not isinstance(item, dict):
                continue
            relative = item.get("path")
            if not isinstance(relative, str) or relative in known:
                continue
            candidate = Path(relative)
            normalized_name = candidate.name.casefold().split(".", 1)[0]
            is_document = item.get("reason") == "non_code_file" and (
                candidate.suffix.casefold() in document_suffixes
                or normalized_name in document_names
            )
            if is_document or sensitive_path_reason(relative) is not None:
                included.append(
                    {"path": relative, "source": item.get("source", "unknown")}
                )
                known.add(relative)
    included.sort(key=lambda item: (item["path"].casefold(), item["path"]))
    return included


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files(
            path TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            size INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks(
            chunk_id TEXT PRIMARY KEY,
            path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
            file_hash TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            vector BLOB NOT NULL,
            norm REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS chunks_path_idx ON chunks(path);
        """
    )
    return connection


def _metadata_compatible(connection: sqlite3.Connection, root: Path) -> bool:
    values = {
        row["key"]: row["value"]
        for row in connection.execute("SELECT key, value FROM metadata")
    }
    expected = {
        "schema_version": str(INDEX_SCHEMA_VERSION),
        "chunker_version": CHUNKER_VERSION,
        "model": ARK_MODEL,
        "dimension": str(EMBEDDING_DIMENSION),
        "repository_root": str(root),
    }
    return values == expected


def _write_metadata(connection: sqlite3.Connection, root: Path) -> None:
    values = {
        "schema_version": str(INDEX_SCHEMA_VERSION),
        "chunker_version": CHUNKER_VERSION,
        "model": ARK_MODEL,
        "dimension": str(EMBEDDING_DIMENSION),
        "repository_root": str(root),
    }
    connection.execute("DELETE FROM metadata")
    connection.executemany(
        "INSERT INTO metadata(key, value) VALUES (?, ?)",
        values.items(),
    )


def _insert_chunk(
    connection: sqlite3.Connection,
    *,
    path: str,
    file_hash: str,
    chunk: TextChunk,
    packed_vector: bytes,
    norm: float,
) -> None:
    chunk_id = hashlib.sha256(
        (f"{path}\0{chunk.start_line}\0{chunk.end_line}\0{chunk.content_hash}").encode()
    ).hexdigest()
    connection.execute(
        """
        INSERT INTO chunks(
            chunk_id, path, file_hash, start_line, end_line,
            content_hash, vector, norm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            path,
            file_hash,
            chunk.start_line,
            chunk.end_line,
            chunk.content_hash,
            packed_vector,
            norm,
        ),
    )


def _pack_vector(vector: list[float]) -> bytes:
    values = array.array("f", vector)
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


def _unpack_vector(value: bytes) -> list[float]:
    values = array.array("f")
    values.frombytes(value)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != EMBEDDING_DIMENSION:
        raise IndexError("Stored embedding has an invalid dimension")
    return values.tolist()


def _norm(vector: list[float]) -> float:
    result = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(result) or result <= 0:
        raise IndexError("Embedding vector has an invalid norm")
    return result


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
