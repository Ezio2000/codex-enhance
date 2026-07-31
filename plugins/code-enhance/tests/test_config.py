from __future__ import annotations

import os
from pathlib import Path

import pytest

from code_enhance_mcp.config import (
    configuration_status,
    load_settings,
)
from code_enhance_mcp.constants import (
    ARK_BASE_URL,
    ARK_MODEL,
    EMBEDDING_DIMENSION,
)
from code_enhance_mcp.errors import ConfigurationError


def test_missing_config_returns_safe_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "missing.toml"
    monkeypatch.setenv("CODE_ENHANCE_CONFIG", str(path))
    monkeypatch.setenv("CODE_ENHANCE_CACHE", str(tmp_path / "cache"))

    status = configuration_status()

    assert status["configured"] is False
    assert status["base_url"] == ARK_BASE_URL
    assert status["model"] == ARK_MODEL
    assert status["dimension"] == EMBEDDING_DIMENSION
    assert "api_key" not in status


def test_loads_private_config_and_cache_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'config_version = 1\n[provider]\napi_key = "private-value"\n',
        encoding="utf-8",
    )
    if os.name == "posix":
        path.chmod(0o600)
    cache = tmp_path / "external-cache"
    monkeypatch.setenv("CODE_ENHANCE_CONFIG", str(path))
    monkeypatch.setenv("CODE_ENHANCE_CACHE", str(cache))

    settings = load_settings()

    assert settings.api_key.get_secret_value() == "private-value"
    assert settings.cache_root == cache.resolve()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
@pytest.mark.parametrize("mode", [0o400, 0o640, 0o700])
def test_requires_exact_private_config_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'config_version = 1\n[provider]\napi_key = "private-value"\n',
        encoding="utf-8",
    )
    path.chmod(mode)
    monkeypatch.setenv("CODE_ENHANCE_CONFIG", str(path))

    with pytest.raises(ConfigurationError, match="chmod 600"):
        load_settings()


def test_validation_error_never_echoes_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "BEGIN-SENSITIVE-CONFIG-VALUE"
    path = tmp_path / "config.toml"
    path.write_text(
        f'config_version = 1\n[provider]\napi_key = "{secret}"\nextra = 1\n',
        encoding="utf-8",
    )
    if os.name == "posix":
        path.chmod(0o600)
    monkeypatch.setenv("CODE_ENHANCE_CONFIG", str(path))

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert secret not in str(caught.value)
