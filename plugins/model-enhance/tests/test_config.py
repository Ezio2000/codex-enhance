from __future__ import annotations

import pytest
from model_enhance_mcp.config import build_provider_settings
from model_enhance_mcp.errors import ConfigurationError


def test_builds_ephemeral_minimax_routes() -> None:
    openai = build_provider_settings(
        protocol="openai",
        base_url="https://api.minimaxi.com/v1/",
        api_key="sk-test",
        model="MiniMax-M3",
    )
    anthropic = build_provider_settings(
        protocol="anthropic",
        base_url="https://api.minimaxi.com/anthropic",
        api_key="sk-test",
        model="MiniMax-M3",
        anthropic_auth_mode="bearer",
    )

    assert openai.base_url == "https://api.minimaxi.com/v1"
    assert openai.auth_mode == "bearer"
    assert anthropic.auth_mode == "bearer"
    assert openai.vendor == anthropic.vendor == "minimax"
    assert "sk-test" not in repr(openai)


def test_anthropic_api_key_defaults_to_x_api_key() -> None:
    settings = build_provider_settings(
        protocol="anthropic",
        base_url="https://anthropic.example/v1",
        api_key="secret",
        model="model",
    )
    assert settings.auth_mode == "x-api-key"


@pytest.mark.parametrize("field", ["api_key", "model"])
def test_rejects_empty_required_values(field: str) -> None:
    values = {
        "protocol": "openai",
        "base_url": "https://router.example/v1",
        "api_key": "secret",
        "model": "model",
    }
    values[field] = "   "
    with pytest.raises(ConfigurationError, match=field):
        build_provider_settings(**values)  # type: ignore[arg-type]


def test_rejects_plain_http_remote_provider() -> None:
    with pytest.raises(ConfigurationError, match="must use HTTPS"):
        build_provider_settings(
            protocol="openai",
            base_url="http://example.com/v1",
            api_key="secret",
            model="model",
        )


def test_rejects_oversized_key_without_echoing_it() -> None:
    marker = "BEGIN_CONFIG_SECRET_" + "x" * 4096 + "_END_CONFIG_SECRET"
    with pytest.raises(ConfigurationError) as captured:
        build_provider_settings(
            protocol="openai",
            base_url="https://router.example/v1",
            api_key=marker,
            model="model",
        )
    assert "BEGIN_CONFIG_SECRET_" not in str(captured.value)
    assert "END_CONFIG_SECRET" not in str(captured.value)


def test_allows_plain_http_loopback_provider() -> None:
    settings = build_provider_settings(
        protocol="openai",
        base_url="http://127.0.0.1:8080/v1",
        api_key="local",
        model="local-model",
    )
    assert settings.vendor == "generic"


def test_rejects_invalid_port_before_http_client() -> None:
    with pytest.raises(ConfigurationError, match="malformed"):
        build_provider_settings(
            protocol="openai",
            base_url="https://router.example:not-a-port/v1",
            api_key="secret",
            model="model",
        )


def test_rejects_malformed_ipv6_as_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="malformed"):
        build_provider_settings(
            protocol="openai",
            base_url="https://[::1",
            api_key="secret",
            model="model",
        )
