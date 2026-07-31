from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import SecretStr

from code_enhance_mcp.client import EmbeddingBatch
from code_enhance_mcp.config import Settings
from code_enhance_mcp.constants import EMBEDDING_DIMENSION
from code_enhance_mcp.schemas import Usage


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        self.calls.append(list(texts))
        vectors = [_vector_for_text(text) for text in texts]
        return EmbeddingBatch(
            vectors=vectors,
            request_id=f"request-{len(self.calls)}",
            usage=Usage(
                prompt_tokens=sum(len(text) for text in texts),
                total_tokens=sum(len(text) for text in texts),
            ),
        )


def _vector_for_text(text: str) -> list[float]:
    lowered = text.casefold()
    vector = [0.0] * EMBEDDING_DIMENSION
    has_auth = any(word in lowered for word in ("auth", "token", "login"))
    vector[0] = 1.0 if has_auth else 0.1
    vector[1] = 1.0 if any(word in lowered for word in ("cache", "index")) else 0.1
    vector[2] = 0.01 + (len(text) % 13) / 100
    return vector


@pytest.fixture
def fake_client() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
    )
    return root


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        config_path=tmp_path / "config.toml",
        cache_root=tmp_path / "cache",
        api_key=SecretStr("test-secret-key"),
    )
