from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from pathlib import Path

import pytest
from conftest import FakeEmbeddingClient

from code_enhance_mcp.errors import ProviderError
from code_enhance_mcp.indexing import search_index, sync_index


def _commit_all(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture"],
        check=True,
    )


@pytest.mark.asyncio
async def test_incremental_index_and_secret_exclusions(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    source = git_repo / "auth.py"
    source.write_text(
        "def authenticate(token):\n    return token == 'ok'\n",
        encoding="utf-8",
    )
    (git_repo / "README.md").write_text("# Authentication docs\n", encoding="utf-8")
    (git_repo / ".env").write_text("API_KEY=do-not-send\n", encoding="utf-8")
    _commit_all(git_repo)

    first = await sync_index(
        settings,
        str(git_repo),
        client=fake_client,
    )
    first_call_count = len(fake_client.calls)
    second = await sync_index(
        settings,
        str(git_repo),
        client=fake_client,
    )

    assert first.files_indexed == 2
    assert first.files_excluded == 1
    assert first.chunks_embedded == 2
    assert second.chunks_embedded == 0
    assert second.files_unchanged == 2
    assert len(fake_client.calls) == first_call_count
    sent = "\n".join(text for call in fake_client.calls for text in call)
    assert "do-not-send" not in sent

    database_bytes = Path(first.index_path).read_bytes()
    assert b"return token" not in database_bytes
    with sqlite3.connect(first.index_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(chunks)")}
    assert "text" not in columns
    assert "source" not in columns


@pytest.mark.asyncio
async def test_changed_and_removed_files_update_atomically(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    first_path = git_repo / "first.py"
    second_path = git_repo / "second.py"
    first_path.write_text("print('first')\n", encoding="utf-8")
    second_path.write_text("print('second')\n", encoding="utf-8")
    _commit_all(git_repo)
    initial = await sync_index(settings, str(git_repo), client=fake_client)

    first_path.write_text("print('first changed auth')\n", encoding="utf-8")
    second_path.unlink()
    updated = await sync_index(settings, str(git_repo), client=fake_client)

    assert initial.files_indexed == 2
    assert updated.files_indexed == 1
    assert updated.files_removed == 1
    assert updated.chunks_embedded == 1


@pytest.mark.asyncio
async def test_changed_file_reuses_unchanged_chunk_vectors(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    source = git_repo / "large_module.py"
    original_lines = [f"value_{number} = {'x' * 60!r}\n" for number in range(1, 301)]
    source.write_text("".join(original_lines), encoding="utf-8")
    _commit_all(git_repo)
    initial = await sync_index(settings, str(git_repo), client=fake_client)
    initial_remote_texts = sum(len(call) for call in fake_client.calls)
    assert initial_remote_texts == initial.chunks_embedded
    assert initial.chunks_embedded > 2

    changed_lines = list(original_lines)
    changed_lines[-1] = "value_300 = 'changed only at the end'\n"
    source.write_text("".join(changed_lines), encoding="utf-8")
    before = sum(len(call) for call in fake_client.calls)
    updated = await sync_index(settings, str(git_repo), client=fake_client)
    after = sum(len(call) for call in fake_client.calls)

    assert updated.chunks_total == initial.chunks_total
    assert updated.chunks_embedded == 1
    assert after - before == 1


@pytest.mark.asyncio
async def test_subpath_sync_preserves_other_index_rows(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    (git_repo / "a").mkdir()
    (git_repo / "b").mkdir()
    (git_repo / "a" / "one.py").write_text("auth token\n", encoding="utf-8")
    (git_repo / "b" / "two.py").write_text("cache index\n", encoding="utf-8")
    _commit_all(git_repo)
    await sync_index(settings, str(git_repo), client=fake_client)

    result = await sync_index(
        settings,
        str(git_repo),
        path="a",
        client=fake_client,
    )

    assert result.files_indexed == 2
    assert result.files_removed == 0


@pytest.mark.asyncio
async def test_search_ranks_and_hash_verifies_current_source(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    auth = git_repo / "auth.py"
    cache = git_repo / "cache.py"
    auth.write_text("def login(token):\n    return verify(token)\n", encoding="utf-8")
    cache.write_text("def cache_index():\n    return {}\n", encoding="utf-8")
    _commit_all(git_repo)
    await sync_index(settings, str(git_repo), client=fake_client)

    found = await search_index(
        settings,
        str(git_repo),
        "where is token authentication handled?",
        top_k=2,
        client=fake_client,
    )

    assert found.matches[0].path == "auth.py"
    assert "login" in found.matches[0].preview

    auth.write_text("def changed_without_refresh():\n    pass\n", encoding="utf-8")
    stale = await search_index(
        settings,
        str(git_repo),
        "token auth",
        top_k=2,
        client=fake_client,
    )
    assert all(match.path != "auth.py" for match in stale.matches)
    assert stale.stale_matches_skipped >= 1


@pytest.mark.asyncio
async def test_failed_refresh_preserves_previous_index(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    source = git_repo / "service.py"
    source.write_text("def old_behavior():\n    return 'stable'\n", encoding="utf-8")
    _commit_all(git_repo)
    initial = await sync_index(settings, str(git_repo), client=fake_client)

    source.write_text("def new_behavior():\n    return 'pending'\n", encoding="utf-8")

    class FailingClient:
        async def embed(self, texts: list[str]):
            raise ProviderError("simulated provider failure")

    with pytest.raises(ProviderError, match="simulated"):
        await sync_index(settings, str(git_repo), client=FailingClient())

    with sqlite3.connect(initial.index_path) as connection:
        stored_hash = connection.execute(
            "SELECT file_hash FROM files WHERE path = 'service.py'"
        ).fetchone()[0]
    assert stored_hash != hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_non_utf8_large_and_symlink_files_are_excluded(
    git_repo: Path,
    settings,
    fake_client: FakeEmbeddingClient,
) -> None:
    outside = git_repo.parent / "outside.py"
    outside.write_text("do not send\n", encoding="utf-8")
    (git_repo / "binary.py").write_bytes(b"\xff\xfe")
    (git_repo / "large.py").write_text("x" * 1_048_577, encoding="utf-8")
    (git_repo / "escape.py").symlink_to(outside)
    _commit_all(git_repo)

    result = await sync_index(settings, str(git_repo), client=fake_client)

    assert result.files_indexed == 0
    assert result.files_excluded == 3
    assert fake_client.calls == []
    assert all("do not send" not in text for call in fake_client.calls for text in call)
