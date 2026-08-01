"""Sanitized public errors for Model Enhance."""

from __future__ import annotations

import re
from collections.abc import Iterable


class ModelEnhanceError(RuntimeError):
    """Base error safe to expose as an MCP tool failure."""


class ConfigurationError(ModelEnhanceError):
    """The server-side provider configuration is missing or invalid."""


class ProviderError(ModelEnhanceError):
    """A compatible upstream returned an invalid or unsuccessful response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InputError(ModelEnhanceError):
    """Selected embedding input or output location is unsafe or invalid."""


_TOKEN_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9._~-]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(x-api-key[\"'\s:=]+)[A-Za-z0-9._~+/=-]+"),
)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove exact secrets and common credential forms from diagnostic text."""

    value = text
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    for pattern in _TOKEN_PATTERNS:
        if pattern.groups:
            value = pattern.sub(r"\1[REDACTED]", value)
        else:
            value = pattern.sub("[REDACTED]", value)
    return value
