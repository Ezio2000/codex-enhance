"""Embedding input orchestration and private JSON artifact writes."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

from .clients import CompatibleModelClient
from .config import ProviderSettings, embedding_cache_root
from .constants import BATCH_SIZE, MAX_ITEM_CHARS, MAX_ITEMS, MAX_TOTAL_CHARS
from .errors import InputError, ProviderError
from .files import read_repository_file, resolve_repository
from .schemas import EmbedArtifactResult, EmbedInput, Usage

_SAFE_ID = re.compile(r"^[^\x00-\x1f\x7f]+$")


async def embed_to_artifact(
    provider: ProviderSettings,
    items: list[EmbedInput],
    *,
    repository: str | None,
    client: CompatibleModelClient | None = None,
) -> EmbedArtifactResult:
    if provider.protocol != "openai":
        raise InputError("Embedding requires protocol='openai'")
    if not 1 <= len(items) <= MAX_ITEMS:
        raise InputError(f"items must contain between 1 and {MAX_ITEMS} entries")
    identifiers = [item.id for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise InputError("item ids must be unique")
    if any(not _SAFE_ID.fullmatch(identifier) for identifier in identifiers):
        raise InputError("item ids must not contain control characters")

    root = resolve_repository(repository) if repository else None
    texts: list[str] = []
    metadata: list[dict[str, str]] = []
    for item in items:
        if item.text is not None:
            text = item.text
            item_metadata = {"id": item.id, "source": "text"}
        else:
            if root is None or item.path is None:
                raise InputError("repository is required for file inputs")
            local = read_repository_file(root, item.path)
            text = local.text
            item_metadata = {
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
        metadata.append(item_metadata)
    if sum(len(text) for text in texts) > MAX_TOTAL_CHARS:
        raise InputError(
            f"Combined input exceeds the {MAX_TOTAL_CHARS} character limit"
        )

    active_client = client or CompatibleModelClient(provider)
    vectors: list[list[float]] = []
    request_ids: list[str] = []
    usages: list[Usage] = []
    actual_model: str | None = None
    dimension: int | None = None
    for offset in range(0, len(texts), BATCH_SIZE):
        batch = await active_client.embed(texts[offset : offset + BATCH_SIZE])
        batch_dimension = len(batch.vectors[0])
        if dimension is not None and dimension != batch_dimension:
            raise ProviderError("Embedding dimensions changed between batches")
        if actual_model is not None and actual_model != batch.model:
            raise ProviderError("Embedding model changed between batches")
        dimension = batch_dimension
        actual_model = batch.model
        vectors.extend(batch.vectors)
        usages.append(batch.usage)
        if batch.request_id:
            request_ids.append(batch.request_id)

    if dimension is None or actual_model is None:
        raise ProviderError("Embedding provider returned no vectors")
    usage = _aggregate_usage(usages)
    artifact_dir = embedding_cache_root() / "embeddings"
    _ensure_outside_repository(artifact_dir, root)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + token_hex(4)
    artifact_path = artifact_dir / f"{run_id}.json"
    payload = {
        "schema": "model-enhance/embed-artifact/v1",
        "protocol": "openai",
        "model": actual_model,
        "dimension": dimension,
        "request_ids": request_ids,
        "usage": usage.model_dump(mode="json"),
        "data": [
            {**item_metadata, "index": index, "embedding": vector}
            for index, (item_metadata, vector) in enumerate(
                zip(metadata, vectors, strict=True)
            )
        ],
    }
    _atomic_json_write(artifact_path, payload)
    return EmbedArtifactResult(
        artifact_path=str(artifact_path),
        protocol="openai",
        model=actual_model,
        dimension=dimension,
        count=len(vectors),
        request_ids=request_ids,
        usage=usage,
    )


def _aggregate_usage(usages: list[Usage]) -> Usage:
    def total(field: str) -> int | None:
        values = [getattr(usage, field) for usage in usages]
        return sum(values) if all(value is not None for value in values) else None

    return Usage(
        input_tokens=total("input_tokens"),
        output_tokens=total("output_tokens"),
        total_tokens=total("total_tokens"),
    )


def _ensure_outside_repository(path: Path, root: Path | None) -> None:
    resolved = path.resolve()
    if root is not None and (resolved == root or root in resolved.parents):
        raise InputError(
            "MODEL_ENHANCE_CACHE must resolve outside the selected repository"
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
