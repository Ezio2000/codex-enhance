"""Versioned local configuration. Secrets are read only from this file."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)

from .errors import ConfigurationError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "video-enhance" / "config.toml"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_provider_base_url(value: str) -> str:
    """Allow HTTPS providers and explicit HTTP loopback development servers."""

    base_url = value.strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        host = (parsed.hostname or "").lower()
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("provider base_url is malformed") from exc
    if (
        not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("provider base_url is malformed")
    if parsed.scheme == "http" and host in _LOOPBACK_HOSTS:
        return base_url
    if parsed.scheme != "https":
        raise ValueError("remote provider base_url must use HTTPS")
    return base_url


class ProviderSettings(BaseModel):
    """Open provider settings envelope; adapters validate their own fields."""

    model_config = ConfigDict(extra="allow")

    type: str
    enabled: bool = True
    api_key: SecretStr | None = None
    base_url: str | None = None
    model: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return validate_provider_base_url(value) if value is not None else None


class SecuritySettings(BaseModel):
    allowed_roots: list[Path] = Field(
        default_factory=lambda: [
            Path.home() / "Desktop",
            Path.home() / ".codex" / "attachments",
        ]
    )
    delete_remote_files: bool = True


class RuntimeSettings(BaseModel):
    max_upload_mb: int = Field(default=512, ge=1, le=4096)


class Settings(BaseModel):
    config_version: int = Field(default=1, ge=1)
    default_provider: str = "minimax"
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    config_path: Path

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        roots = tuple(
            path.expanduser().resolve() for path in self.security.allowed_roots
        )
        if not roots:
            raise ConfigurationError("security.allowed_roots must not be empty")
        return roots


def config_path() -> Path:
    override = os.environ.get("VIDEO_ENHANCE_CONFIG")
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_PATH


def load_settings(*, require_file: bool = False) -> Settings:
    path = config_path()
    if not path.is_file():
        if require_file:
            raise ConfigurationError(
                f"CONFIG_REQUIRED: create {path} and configure a video provider"
            )
        return Settings(config_path=path)

    if os.name == "posix":
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            raise ConfigurationError(
                f"Unsafe permissions on {path}: use chmod 600 so API keys stay private"
            )
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        settings = Settings.model_validate({**raw, "config_path": path})
    except ValidationError as exc:
        safe_errors = exc.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
        raise ConfigurationError(
            f"Invalid Video Enhance config at {path}: {safe_errors}"
        ) from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(
            f"Invalid Video Enhance config at {path}: {exc}"
        ) from exc
    if settings.config_version != 1:
        raise ConfigurationError(
            f"Unsupported config_version {settings.config_version}; expected 1"
        )
    _ = settings.allowed_roots
    return settings


def ensure_provider_config(
    settings: Settings, requested: str
) -> tuple[str, ProviderSettings]:
    name = settings.default_provider if requested == "auto" else requested
    provider = settings.providers.get(name)
    if provider is None:
        raise ConfigurationError(
            f"CONFIG_REQUIRED: provider {name!r} is not configured in {settings.config_path}"
        )
    if not provider.enabled:
        raise ConfigurationError(
            f"Provider {name!r} is disabled in {settings.config_path}"
        )
    if provider.api_key is None or not provider.api_key.get_secret_value().strip():
        raise ConfigurationError(
            f"CONFIG_REQUIRED: providers.{name}.api_key is missing in {settings.config_path}"
        )
    return name, provider
