from __future__ import annotations

import os
from pathlib import Path

import pytest

from video_enhance_mcp import config as config_module
from video_enhance_mcp.config import (
    ProviderSettings,
    config_path,
    ensure_provider_config,
    load_settings,
    validate_provider_base_url,
)
from video_enhance_mcp.errors import ConfigurationError
from video_enhance_mcp.server import video_config_status


def _write_config(path: Path, *, mode: int = 0o600) -> None:
    path.write_text(
        """config_version = 1
default_provider = "minimax"
[providers.minimax]
type = "minimax"
api_key = "test-token-never-log"
base_url = "https://api.minimaxi.com/v1"
model = "MiniMax-M3"
[security]
allowed_roots = ["~/Desktop"]
""",
        encoding="utf-8",
    )
    path.chmod(mode)


@pytest.fixture(autouse=True)
def _clear_config_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEO_ENHANCE_CONFIG", raising=False)
    monkeypatch.delenv("VIDEO_MCP_CONFIG", raising=False)


def test_config_file_loads_secret_as_secret_str(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    _write_config(path)
    monkeypatch.setenv("VIDEO_ENHANCE_CONFIG", str(path))
    settings = load_settings(require_file=True)
    _, provider = ensure_provider_config(settings, "auto")
    assert provider.api_key is not None
    assert provider.api_key.get_secret_value() == "test-token-never-log"
    assert "test-token-never-log" not in repr(provider.api_key)


def test_missing_config_allows_inspect_defaults_but_analysis_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "missing.toml"
    monkeypatch.setenv("VIDEO_ENHANCE_CONFIG", str(path))
    assert load_settings(require_file=False).providers == {}
    with pytest.raises(ConfigurationError, match="CONFIG_REQUIRED"):
        load_settings(require_file=True)


@pytest.mark.skipif(
    os.name != "posix", reason="POSIX permission bits are not portable to Windows"
)
def test_config_with_open_permissions_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    _write_config(path, mode=0o644)
    monkeypatch.setenv("VIDEO_ENHANCE_CONFIG", str(path))
    with pytest.raises(ConfigurationError, match="chmod 600"):
        load_settings(require_file=True)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.minimaxi.com/v1",
        "https://user:password@api.minimaxi.com/v1",
        "https://api.minimaxi.com/v1?token=value",
        "https://api.minimaxi.com/v1#fragment",
        "https://api.minimaxi.com:invalid/v1",
    ],
)
def test_provider_base_url_rejects_unsafe_routes(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        validate_provider_base_url(base_url)


def test_provider_base_url_allows_https_and_explicit_http_loopback() -> None:
    remote = ProviderSettings(
        type="minimax",
        base_url="https://api.minimaxi.com/v1/",
    )
    loopback = ProviderSettings(
        type="minimax",
        base_url="http://localhost:8080/v1/",
    )

    assert remote.base_url == "https://api.minimaxi.com/v1"
    assert loopback.base_url == "http://localhost:8080/v1"


def test_invalid_api_key_type_is_not_echoed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "malformed-secret-must-not-leak"
    path = tmp_path / "config.toml"
    path.write_text(
        f"""config_version = 1
default_provider = "minimax"
[providers.minimax]
type = "minimax"
api_key = ["{secret}"]
""",
        encoding="utf-8",
    )
    path.chmod(0o600)
    monkeypatch.setenv("VIDEO_ENHANCE_CONFIG", str(path))

    with pytest.raises(ConfigurationError) as error:
        load_settings(require_file=True)

    assert secret not in str(error.value)


@pytest.mark.asyncio
async def test_config_status_exposes_remote_deletion_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    _write_config(path)
    contents = path.read_text(encoding="utf-8").replace(
        'allowed_roots = ["~/Desktop"]',
        'allowed_roots = ["~/Desktop"]\ndelete_remote_files = false',
    )
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv("VIDEO_ENHANCE_CONFIG", str(path))

    status = await video_config_status()

    assert status.ready is True
    assert status.delete_remote_files is False


def test_new_environment_override_wins_over_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_path = tmp_path / "new.toml"
    legacy_path = tmp_path / "legacy.toml"
    monkeypatch.setenv("VIDEO_ENHANCE_CONFIG", str(new_path))
    monkeypatch.setenv("VIDEO_MCP_CONFIG", str(legacy_path))
    assert config_path() == new_path


def test_legacy_environment_override_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_path = tmp_path / "legacy.toml"
    monkeypatch.setenv("VIDEO_MCP_CONFIG", str(legacy_path))
    assert config_path() == legacy_path


def test_existing_new_default_wins_over_existing_legacy_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_path = tmp_path / "video-enhance" / "config.toml"
    legacy_path = tmp_path / "video-mcp" / "config.toml"
    new_path.parent.mkdir()
    legacy_path.parent.mkdir()
    new_path.touch()
    legacy_path.touch()
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", new_path)
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy_path)
    assert config_path() == new_path


def test_existing_legacy_default_is_used_when_new_default_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_path = tmp_path / "video-enhance" / "config.toml"
    legacy_path = tmp_path / "video-mcp" / "config.toml"
    legacy_path.parent.mkdir()
    legacy_path.touch()
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", new_path)
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy_path)
    assert config_path() == legacy_path


def test_new_default_is_returned_when_neither_default_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_path = tmp_path / "video-enhance" / "config.toml"
    legacy_path = tmp_path / "video-mcp" / "config.toml"
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", new_path)
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy_path)
    assert config_path() == new_path
