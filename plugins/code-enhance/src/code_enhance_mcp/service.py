"""Embedding artifact orchestration shared by MCP tools."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

from .client import ArkEmbeddingClient
from .config import Settings
from .constants import (
    ARK_MODEL,
    BATCH_SIZE,
    EMBEDDING_DIMENSION,
    MAX_ITEM_CHARS,
    MAX_ITEMS,
    MAX_TOTAL_CHARS,
)
from .errors import InputError
from .files import read_repository_file, resolve_repository
from .schemas import EmbedArtifactResult, EmbedInput, Usage

_SAFE_ID = re.compile(r"^[^\x00-\x1f\x7f]+$")


async def embed_to_artifact(
    settings: Settings,
    items: list[EmbedInput],
    *,
    repository: str | None,
    client: ArkEmbeddingClient | None = None,
) -> EmbedArtifactResult:
    if not 1 <= len(items) <= MAX_ITEMS:
        raise InputError(f"items must contain between 1 and {MAX_ITEMS} entries")
    identifiers = [item.id for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise InputError("item ids must be unique")
    if any(not _SAFE_ID.fullmatch(identifier) for identifier in identifiers):
        raise InputError("item ids must not contain control characters")

    root = resolve_repository(repository) if repository else None
    texts: list[str] = []
    item_metadata: list[dict[str, str]] = []
    for item in items:
        if item.text is not None:
            text = item.text
            metadata = {"id": item.id, "source": "text"}
        else:
            if root is None or item.path is None:
                raise InputError("repository is required for file inputs")
            local = read_repository_file(root, item.path)
            text = local.text
            metadata = {
                "id": item.id,
                "source": "file",
                "path": local.relative_path,
                "file_hash": local.file_hash,
            }
        if len(text) > MAX_ITEM_CHARS:
            raise InputError(
                f"Input {item.id!r} exceeds the {MAX_ITEM_CHARS} character limit"
            )
        texts.append(text)
        item_metadata.append(metadata)
    if sum(len(text) for text in texts) > MAX_TOTAL_CHARS:
        raise InputError(
            f"Combined input exceeds the {MAX_TOTAL_CHARS} character limit"
        )

    active_client = client or ArkEmbeddingClient(settings.api_key)
    vectors: list[list[float]] = []
    request_ids: list[str] = []
    prompt_tokens = 0
    total_tokens = 0
    prompt_known = True
    total_known = True
    for offset in range(0, len(texts), BATCH_SIZE):
        batch = await active_client.embed(texts[offset : offset + BATCH_SIZE])
        vectors.extend(batch.vectors)
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

    artifact_dir = settings.cache_root / "embed"
    _ensure_outside_repository(artifact_dir, root)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + token_hex(4)
    artifact_path = artifact_dir / f"{run_id}.json"
    payload = {
        "schema": "code-enhance/embed-artifact/v1",
        "model": ARK_MODEL,
        "dimension": EMBEDDING_DIMENSION,
        "request_ids": request_ids,
        "usage": {
            "prompt_tokens": prompt_tokens if prompt_known else None,
            "total_tokens": total_tokens if total_known else None,
        },
        "data": [
            {
                **metadata,
                "index": index,
                "embedding": vector,
            }
            for index, (metadata, vector) in enumerate(
                zip(item_metadata, vectors, strict=True)
            )
        ],
    }
    _atomic_json_write(artifact_path, payload)
    return EmbedArtifactResult(
        artifact_path=str(artifact_path),
        model=ARK_MODEL,
        dimension=EMBEDDING_DIMENSION,
        count=len(vectors),
        request_ids=request_ids,
        usage=Usage(
            prompt_tokens=prompt_tokens if prompt_known else None,
            total_tokens=total_tokens if total_known else None,
        ),
    )


def _ensure_outside_repository(path: Path, root: Path | None) -> None:
    resolved = path.resolve()
    if root is not None and (resolved == root or root in resolved.parents):
        raise InputError(
            "CODE_ENHANCE_CACHE must resolve outside the indexed repository"
        )


def _atomic_json_write(path: Path, payload: object) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "posix":
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
