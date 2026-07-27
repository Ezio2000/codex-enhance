"""Configured provider factory registry."""

from __future__ import annotations

from collections.abc import Callable

from ..config import ProviderSettings, Settings, ensure_provider_config
from ..core.contracts import VideoProvider
from ..errors import ConfigurationError
from .minimax import MiniMaxProvider

ProviderFactory = Callable[[ProviderSettings, bool], VideoProvider]


def _minimax_factory(settings: ProviderSettings, delete_remote: bool) -> VideoProvider:
    return MiniMaxProvider(settings, delete_remote_files=delete_remote)


FACTORIES: dict[str, ProviderFactory] = {"minimax": _minimax_factory}


def create_provider(settings: Settings, requested: str) -> tuple[str, VideoProvider]:
    name, provider_settings = ensure_provider_config(settings, requested)
    factory = FACTORIES.get(provider_settings.type)
    if factory is None:
        supported = ", ".join(sorted(FACTORIES))
        raise ConfigurationError(
            f"Provider type {provider_settings.type!r} is unsupported; available types: {supported}"
        )
    return name, factory(provider_settings, settings.security.delete_remote_files)
