from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import FakeEmbeddingClient

from code_enhance_mcp.errors import InputError
from code_enhance_mcp.schemas import EmbedInput
from code_enhance_mcp.service import embed_to_artifact


@pytest.mark.asyncio
async def test_embed_writes_vectors_without_copying_source(
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    secret_source = "auth implementation text that should not be stored"
    result = await embed_to_artifact(
        settings,
        [EmbedInput(id="auth", text=secret_source)],
        repository=None,
        client=fake_client,
    )

    artifact = Path(result.artifact_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert artifact.is_file()
    assert payload["dimension"] == 1024
    assert len(payload["data"][0]["embedding"]) == 1024
    assert secret_source not in artifact.read_text(encoding="utf-8")
    assert settings.api_key.get_secret_value() not in artifact.read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_embed_batches_at_provider_limit(settings, fake_client) -> None:
    await embed_to_artifact(
        settings,
        [EmbedInput(id=f"item-{index}", text=f"text {index}") for index in range(11)],
        repository=None,
        client=fake_client,
    )

    assert [len(call) for call in fake_client.calls] == [10, 1]


@pytest.mark.asyncio
async def test_embed_file_requires_repository(settings, fake_client) -> None:
    with pytest.raises(InputError, match="repository is required"):
        await embed_to_artifact(
            settings,
            [EmbedInput(id="file", path="source.py")],
            repository=None,
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_embed_rejects_duplicate_ids(settings, fake_client) -> None:
    with pytest.raises(InputError, match="unique"):
        await embed_to_artifact(
            settings,
            [
                EmbedInput(id="same", text="one"),
                EmbedInput(id="same", text="two"),
            ],
            repository=None,
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_embed_rejects_cache_inside_repository(
    git_repo: Path,
    settings,
    fake_client,
) -> None:
    unsafe_settings = settings.model_copy(
        update={"cache_root": git_repo / ".code-enhance-cache"}
    )

    with pytest.raises(InputError, match="outside"):
        await embed_to_artifact(
            unsafe_settings,
            [EmbedInput(id="text", text="selected text")],
            repository=str(git_repo),
            client=fake_client,
        )
