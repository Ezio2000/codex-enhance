from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from model_enhance_mcp.clients import EmbeddingBatch
from model_enhance_mcp.config import ProviderSettings
from model_enhance_mcp.embeddings import embed_to_artifact
from model_enhance_mcp.errors import InputError, ProviderError
from model_enhance_mcp.schemas import EmbedInput, Usage
from pydantic import SecretStr


class FakeEmbeddingClient:
    def __init__(self, *, dimensions: list[int] | None = None) -> None:
        self.dimensions = dimensions or [3]
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        self.calls.append(texts)
        dimension = self.dimensions[len(self.calls) - 1]
        return EmbeddingBatch(
            vectors=[[float(index + 1)] * dimension for index in range(len(texts))],
            model="provider-embed-model",
            request_id=f"request-{len(self.calls)}",
            usage=Usage(input_tokens=len(texts), total_tokens=len(texts)),
        )


@pytest.fixture
def provider() -> ProviderSettings:
    return ProviderSettings(
        protocol="openai",
        base_url="https://embedding.example/v1",
        api_key=SecretStr("private-key"),
        model="requested-model",
        auth_mode="bearer",
        vendor="generic",
        timeout_seconds=10,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "source.py").write_text("print('safe')\n", encoding="utf-8")
    return root


@pytest.mark.asyncio
async def test_writes_private_artifact_without_source_or_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: ProviderSettings,
) -> None:
    monkeypatch.setenv("MODEL_ENHANCE_CACHE", str(tmp_path / "cache"))
    source = "selected source text that must not be copied"
    result = await embed_to_artifact(
        provider,
        [EmbedInput(id="selected", text=source)],
        repository=None,
        client=FakeEmbeddingClient(),  # type: ignore[arg-type]
    )

    artifact = Path(result.artifact_path)
    raw = artifact.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["schema"] == "model-enhance/embed-artifact/v1"
    assert payload["protocol"] == "openai"
    assert payload["dimension"] == 3
    assert payload["data"][0]["embedding"] == [1.0, 1.0, 1.0]
    assert source not in raw
    assert provider.api_key.get_secret_value() not in raw
    if os.name == "posix":
        assert artifact.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_reads_safe_repository_file_and_preserves_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: ProviderSettings,
    git_repo: Path,
) -> None:
    monkeypatch.setenv("MODEL_ENHANCE_CACHE", str(tmp_path / "cache"))
    result = await embed_to_artifact(
        provider,
        [EmbedInput(id="source", path="source.py")],
        repository=str(git_repo),
        client=FakeEmbeddingClient(),  # type: ignore[arg-type]
    )
    payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    item = payload["data"][0]
    assert item["path"] == "source.py"
    assert len(item["file_hash"]) == 64
    assert "print('safe')" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_batches_sixteen_items_and_aggregates_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: ProviderSettings,
) -> None:
    monkeypatch.setenv("MODEL_ENHANCE_CACHE", str(tmp_path / "cache"))
    client = FakeEmbeddingClient(dimensions=[3, 3])
    result = await embed_to_artifact(
        provider,
        [EmbedInput(id=str(index), text="text") for index in range(17)],
        repository=None,
        client=client,  # type: ignore[arg-type]
    )
    assert [len(call) for call in client.calls] == [16, 1]
    assert result.count == 17
    assert result.request_ids == ["request-1", "request-2"]
    assert result.usage.input_tokens == 17


@pytest.mark.asyncio
async def test_rejects_duplicate_ids_missing_repository_and_unsafe_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: ProviderSettings,
    git_repo: Path,
) -> None:
    client = FakeEmbeddingClient()
    with pytest.raises(InputError, match="unique"):
        await embed_to_artifact(
            provider,
            [EmbedInput(id="same", text="one"), EmbedInput(id="same", text="two")],
            repository=None,
            client=client,  # type: ignore[arg-type]
        )
    with pytest.raises(InputError, match="repository is required"):
        await embed_to_artifact(
            provider,
            [EmbedInput(id="file", path="source.py")],
            repository=None,
            client=client,  # type: ignore[arg-type]
        )

    monkeypatch.setenv("MODEL_ENHANCE_CACHE", str(git_repo / ".cache"))
    with pytest.raises(InputError, match="outside"):
        await embed_to_artifact(
            provider,
            [EmbedInput(id="file", path="source.py")],
            repository=str(git_repo),
            client=client,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_rejects_dimension_changes_between_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: ProviderSettings,
) -> None:
    monkeypatch.setenv("MODEL_ENHANCE_CACHE", str(tmp_path / "cache"))
    with pytest.raises(ProviderError, match="dimensions changed"):
        await embed_to_artifact(
            provider,
            [EmbedInput(id=str(index), text="text") for index in range(17)],
            repository=None,
            client=FakeEmbeddingClient(dimensions=[3, 4]),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_rejects_combined_input_over_one_million_characters(
    provider: ProviderSettings,
) -> None:
    with pytest.raises(InputError, match="Combined input"):
        await embed_to_artifact(
            provider,
            [EmbedInput(id=str(index), text="x" * 100_000) for index in range(11)],
            repository=None,
            client=FakeEmbeddingClient(),  # type: ignore[arg-type]
        )
