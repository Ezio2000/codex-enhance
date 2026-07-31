"""Sanitized public errors."""

from __future__ import annotations

import re
from collections.abc import Iterable


class CodeEnhanceError(RuntimeError):
    """Base error safe to expose through MCP."""


class ConfigurationError(CodeEnhanceError):
    """Local provider configuration is missing or unsafe."""


class ProviderError(CodeEnhanceError):
    """The locked upstream returned an invalid or unsuccessful response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InputError(CodeEnhanceError):
    """The requested local input is outside the supported boundary."""


class IndexError(CodeEnhanceError):
    """The local semantic index is missing or invalid."""


_TOKEN_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key[\"'\s:=]+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b(?:AKLT|sk-)[A-Za-z0-9._~-]{8,}\b"),
)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove exact credentials and common credential-shaped values."""

    value = text
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    for pattern in _TOKEN_PATTERNS:
        value = pattern.sub(
            r"\1[REDACTED]" if pattern.groups else "[REDACTED]",
            value,
        )
    return value
