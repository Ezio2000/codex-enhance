import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from video_enhance_mcp.config import ProviderSettings, Settings
from video_enhance_mcp.errors import ConfigurationError, ProviderError
from video_enhance_mcp.providers.minimax.adapter import PROFILES, MiniMaxProvider
from video_enhance_mcp.providers.minimax.client import (
    MiniMaxClient,
    UploadedFile,
    analysis_tool_definition,
    tool_arguments_content,
)
from video_enhance_mcp.providers.registry import create_provider


def test_minimax_capabilities_and_profile_mapping() -> None:
    provider = MiniMaxProvider(
        ProviderSettings(type="minimax", api_key="secret"), delete_remote_files=True
    )
    capabilities = provider.capabilities()
    assert capabilities.supported_formats == ("mp4",)
    assert capabilities.supports_structured_output is True
    assert PROFILES["temporal"].fps == 5.0
    assert PROFILES["ocr"].detail == "high"


def test_minimax_tool_uses_a_flat_payload_envelope() -> None:
    parameters = analysis_tool_definition()["function"]["parameters"]
    assert parameters["required"] == ["payload"]
    assert parameters["properties"]["payload"]["type"] == "string"


def test_minimax_tool_unwraps_string_and_dict_arguments() -> None:
    payload = '{"summary":"ok"}'
    assert tool_arguments_content({"payload": payload}) == payload
    assert tool_arguments_content('{"payload":"{\\"summary\\":\\"ok\\"}"}') == payload


def test_registry_rejects_unknown_provider_type(tmp_path: Path) -> None:
    settings = Settings(
        config_path=tmp_path / "config.toml",
        providers={"future": ProviderSettings(type="future", api_key="secret")},
        default_provider="future",
    )
    with pytest.raises(ConfigurationError, match="unsupported"):
        create_provider(settings, "auto")


@pytest.mark.asyncio
async def test_minimax_client_refuses_redirects() -> None:
    async with MiniMaxClient(
        base_url="https://api.minimaxi.com/v1",
        api_key=SecretStr("secret"),
    ) as client:
        assert client._client.follow_redirects is False
        response = httpx.Response(
            307,
            headers={"location": "https://redirect.example/upload"},
            json={"base_resp": {"status_code": 0}},
        )
        with pytest.raises(ProviderError, match="refused HTTP redirect 307"):
            client._checked_payload(response)


@pytest.mark.asyncio
async def test_provider_errors_redact_before_preview_truncation() -> None:
    secret = "BOUNDARYTOKEN-MUST-NOT-LEAK"
    async with MiniMaxClient(
        base_url="https://api.minimaxi.com/v1",
        api_key=SecretStr(secret),
    ) as client:
        text_response = httpx.Response(502, text="x" * 995 + secret)
        with pytest.raises(ProviderError) as text_error:
            client._checked_payload(text_response)

        template = {
            "base_resp": {"status_code": 1},
            "message": secret,
        }
        prefix_length = json.dumps(template).index(secret)
        payload = {
            "base_resp": {"status_code": 1},
            "message": "x" * (1995 - prefix_length) + secret,
        }
        json_response = httpx.Response(400, json=payload)
        with pytest.raises(ProviderError) as json_error:
            client._checked_payload(json_response)

    assert secret[:5] not in str(text_error.value)
    assert secret[:5] not in str(json_error.value)


@pytest.mark.asyncio
async def test_analysis_and_cleanup_failures_disclose_retention_without_secrets(
    tmp_path: Path,
) -> None:
    secret = "cleanup-boundary-secret"
    async with MiniMaxClient(
        base_url="https://api.minimaxi.com/v1",
        api_key=SecretStr(secret),
    ) as client:
        client.upload_video = AsyncMock(return_value=UploadedFile(file_id="file-1"))
        client.delete_video = AsyncMock(
            side_effect=ProviderError(f"cleanup rejected {secret}")
        )

        with pytest.raises(ProviderError) as error:
            async with client.temporary_upload(
                tmp_path / "video.mp4",
                delete_remote=True,
            ):
                raise ProviderError(f"analysis rejected {secret}")

    message = str(error.value)
    assert "uploaded file may remain" in message
    assert secret not in message


@pytest.mark.asyncio
async def test_disabled_remote_deletion_returns_retention_warning(
    tmp_path: Path,
) -> None:
    async with MiniMaxClient(
        base_url="https://api.minimaxi.com/v1",
        api_key=SecretStr("secret"),
    ) as client:
        client.upload_video = AsyncMock(return_value=UploadedFile(file_id="file-1"))
        client.delete_video = AsyncMock()

        async with client.temporary_upload(
            tmp_path / "video.mp4",
            delete_remote=False,
        ) as uploaded:
            pass

    assert uploaded.cleanup_warning is not None
    assert "delete_remote_files=false" in uploaded.cleanup_warning
    client.delete_video.assert_not_awaited()
