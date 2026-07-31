"""Versioned private configuration and cache resolution."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from .constants import (
    ARK_BASE_URL,
    ARK_MODEL,
    CONFIG_VERSION,
    EMBEDDING_DIMENSION,
)
from .errors import ConfigurationError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "code-enhance" / "config.toml"
DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "code-enhance"


class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr


class ConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_version: int = Field(default=CONFIG_VERSION, ge=1)
    provider: ProviderSettings


class Settings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    config_path: Path
    cache_root: Path
    api_key: SecretStr


def config_path() -> Path:
    override = os.environ.get("CODE_ENHANCE_CONFIG", "").strip()
    return Path(override).expanduser() if override else DEFAULT_CONFIG_PATH


def cache_root() -> Path:
    override = os.environ.get("CODE_ENHANCE_CACHE", "").strip()
    return (
        Path(override).expanduser().resolve()
        if override
        else DEFAULT_CACHE_ROOT.resolve()
    )


def configuration_status() -> dict[str, object]:
    path = config_path()
    root = cache_root()
    error: str | None = None
    configured = False
    try:
        _ = load_settings()
        configured = True
    except ConfigurationError as exc:
        error = str(exc)
    return {
        "configured": configured,
        "config_path": str(path),
        "cache_root": str(root),
        "base_url": ARK_BASE_URL,
        "model": ARK_MODEL,
        "dimension": EMBEDDING_DIMENSION,
        "error": error,
    }


def load_settings() -> Settings:
    path = config_path()
    if not path.is_file():
        raise ConfigurationError(
            f"CONFIG_REQUIRED: create {path} from config.example.toml"
        )
    if os.name == "posix":
        mode = path.stat().st_mode & 0o777
        if mode != 0o600:
            raise ConfigurationError(f"Unsafe permissions on {path}: use chmod 600")
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        parsed = ConfigFile.model_validate(raw)
    except ValidationError as exc:
        safe_errors = exc.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
        raise ConfigurationError(
            f"Invalid Code Enhance config at {path}: {safe_errors}"
        ) from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(
            f"Invalid Code Enhance config at {path}: {exc}"
        ) from exc
    if parsed.config_version != CONFIG_VERSION:
        raise ConfigurationError(
            f"Unsupported config_version {parsed.config_version}; "
            f"expected {CONFIG_VERSION}"
        )
    key = parsed.provider.api_key.get_secret_value().strip()
    if not key:
        raise ConfigurationError(f"provider.api_key is empty in {path}")
    return Settings(
        config_path=path,
        cache_root=cache_root(),
        api_key=SecretStr(key),
    )
