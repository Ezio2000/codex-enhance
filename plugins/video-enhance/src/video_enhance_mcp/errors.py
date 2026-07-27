"""Typed and sanitized errors safe to expose through MCP."""

from __future__ import annotations

import re


class VideoEnhanceError(RuntimeError):
    """Base class for expected Video Enhance failures."""


class ConfigurationError(VideoEnhanceError):
    """Configuration is absent, invalid, or unsafe."""


class MediaError(VideoEnhanceError):
    """Input media cannot be accessed, probed, or normalized."""


class ProviderError(VideoEnhanceError):
    """A configured video provider rejected or failed a request."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


_TOKEN_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
)


def redact(text: str, secret: str | None = None) -> str:
    """Remove common credential forms and an exact loaded secret."""

    value = text
    if secret:
        value = value.replace(secret, "[REDACTED]")
    for pattern in _TOKEN_PATTERNS:
        value = pattern.sub(r"\1[REDACTED]" if pattern.groups else "[REDACTED]", value)
    return value
