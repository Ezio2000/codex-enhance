"""Validate per-call connection parameters supplied by the MCP caller."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr

from .errors import ConfigurationError
from .schemas import ProtocolName

AuthMode = Literal["bearer", "x-api-key"]
Vendor = Literal["generic", "minimax"]

_MINIMAX_HOSTS = frozenset({"api.minimax.io", "api.minimaxi.com"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "model-enhance"


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    protocol: ProtocolName
    base_url: str
    api_key: SecretStr
    model: str
    auth_mode: AuthMode
    vendor: Vendor
    timeout_seconds: float = 180


def embedding_cache_root() -> Path:
    """Resolve the non-credential cache root used for embedding artifacts."""

    override = os.environ.get("MODEL_ENHANCE_CACHE", "").strip()
    selected = Path(override).expanduser() if override else DEFAULT_CACHE_ROOT
    return selected.resolve()


def build_provider_settings(
    *,
    protocol: ProtocolName,
    base_url: str,
    api_key: str,
    model: str,
    anthropic_auth_mode: AuthMode = "x-api-key",
    timeout_seconds: float = 180,
) -> ProviderSettings:
    """Build one ephemeral route; credentials are never loaded or persisted here."""

    normalized_key = api_key.strip()
    normalized_model = model.strip()
    if not normalized_key:
        raise ConfigurationError("api_key must not be empty")
    # Check only after FastMCP/Pydantic has converted the input to SecretStr.
    # Pre-conversion Field length errors can echo the original secret in the
    # validation failure returned to the MCP caller.
    if len(normalized_key) > 4096:
        raise ConfigurationError("api_key exceeds the maximum supported length")
    if not normalized_model:
        raise ConfigurationError("model must not be empty")
    if not 1 <= timeout_seconds <= 3600:
        raise ConfigurationError("timeout_seconds must be between 1 and 3600")
    if anthropic_auth_mode not in {"bearer", "x-api-key"}:
        raise ConfigurationError("anthropic_auth_mode must be 'bearer' or 'x-api-key'")

    validated_base = validate_base_url(base_url)
    host = (urlsplit(validated_base).hostname or "").lower()
    vendor: Vendor = "minimax" if host in _MINIMAX_HOSTS else "generic"
    return ProviderSettings(
        protocol=protocol,
        base_url=validated_base,
        api_key=SecretStr(normalized_key),
        model=normalized_model,
        auth_mode="bearer" if protocol == "openai" else anthropic_auth_mode,
        vendor=vendor,
        timeout_seconds=timeout_seconds,
    )


def validate_base_url(value: str) -> str:
    """Allow HTTPS providers and explicit HTTP loopback development servers."""

    base_url = value.strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        host = (parsed.hostname or "").lower()
        _ = parsed.port
    except ValueError as exc:
        raise ConfigurationError("Provider base URL is malformed") from exc
    if (
        not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError("Provider base URL is malformed")
    if parsed.scheme == "http" and host in _LOOPBACK_HOSTS:
        return base_url
    if parsed.scheme != "https":
        raise ConfigurationError("Remote provider base URLs must use HTTPS")
    return base_url
