from __future__ import annotations

import json

import httpx
import pytest
from model_enhance_mcp.clients import CompatibleModelClient
from model_enhance_mcp.config import ProviderSettings
from model_enhance_mcp.errors import ProviderError
from pydantic import SecretStr


def _settings(
    protocol: str,
    *,
    secret: str = "sk-cp-test-secret",
    vendor: str = "generic",
    auth_mode: str = "bearer",
) -> ProviderSettings:
    return ProviderSettings(  # type: ignore[arg-type]
        protocol=protocol,
        base_url=(
            "https://api.minimaxi.com/v1"
            if protocol == "openai"
            else "https://api.minimaxi.com/anthropic"
        ),
        api_key=SecretStr(secret),
        model="MiniMax-M3",
        auth_mode=auth_mode,
        vendor=vendor,
        timeout_seconds=10,
    )


@pytest.mark.asyncio
async def test_openai_chat_request_and_response_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer sk-cp-test-secret"
        body = json.loads(request.content)
        assert body["model"] == "MiniMax-M3"
        assert body["messages"] == [
            {"role": "system", "content": "Be terse."},
            {"role": "user", "content": "Say OK"},
        ]
        assert body["max_completion_tokens"] == 64
        assert body["thinking"] == {"type": "disabled"}
        return httpx.Response(
            200,
            json={
                "id": "openai-request",
                "model": "MiniMax-M3",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "<think>private reasoning</think>\nOK",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 1,
                    "total_tokens": 5,
                },
            },
        )

    client = CompatibleModelClient(
        _settings("openai", vendor="minimax"),
        transport=httpx.MockTransport(handler),
    )
    result = await client.ask(
        prompt="Say OK",
        system_prompt="Be terse.",
        max_output_tokens=64,
        temperature=0.1,
    )

    assert result.text == "OK"
    assert "private reasoning" not in result.text
    assert result.usage.total_tokens == 5
    assert result.request_id == "openai-request"


@pytest.mark.asyncio
async def test_anthropic_messages_request_and_response_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/anthropic/v1/messages"
        assert request.headers["x-api-key"] == "sk-cp-test-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["system"] == "Be terse."
        assert body["messages"] == [{"role": "user", "content": "Say OK"}]
        return httpx.Response(
            200,
            json={
                "id": "anthropic-request",
                "type": "message",
                "model": "MiniMax-M3",
                "stop_reason": "end_turn",
                "content": [
                    {"type": "thinking", "thinking": "private reasoning"},
                    {"type": "text", "text": "OK"},
                ],
                "usage": {"input_tokens": 4, "output_tokens": 1},
            },
        )

    client = CompatibleModelClient(
        _settings("anthropic", auth_mode="x-api-key"),
        transport=httpx.MockTransport(handler),
    )
    result = await client.ask(
        prompt="Say OK",
        system_prompt="Be terse.",
        max_output_tokens=64,
        temperature=None,
    )

    assert result.text == "OK"
    assert "private reasoning" not in result.text
    assert result.usage.total_tokens == 5
    assert result.warnings == []


@pytest.mark.asyncio
async def test_anthropic_bearer_auth_mode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk-cp-test-secret"
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json={"data": []})

    models = await CompatibleModelClient(
        _settings("anthropic", auth_mode="bearer"),
        transport=httpx.MockTransport(handler),
    ).list_models()

    assert models == []


@pytest.mark.asyncio
async def test_provider_errors_are_redacted() -> None:
    secret = "sk-cp-never-show-this"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": f"invalid bearer {secret}"}},
        )

    client = CompatibleModelClient(
        _settings("openai", secret=secret),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError) as caught:
        await client.ask(
            prompt="test",
            system_prompt=None,
            max_output_tokens=16,
            temperature=None,
        )

    assert secret not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


@pytest.mark.asyncio
async def test_redaction_happens_before_error_truncation() -> None:
    secret = "NONSTANDARD-VERY-SENSITIVE-KEY"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": ("x" * 990) + secret + "tail"}},
        )

    client = CompatibleModelClient(
        _settings("openai", secret=secret),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError) as caught:
        await client.ask(
            prompt="test",
            system_prompt=None,
            max_output_tokens=16,
            temperature=None,
        )

    assert secret[:12] not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


@pytest.mark.asyncio
async def test_remote_model_listing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={"data": [{"id": "MiniMax-M3"}, {"id": "MiniMax-M2.7"}]},
        )

    models = await CompatibleModelClient(
        _settings("openai"), transport=httpx.MockTransport(handler)
    ).list_models()
    assert models == ["MiniMax-M2.7", "MiniMax-M3"]


@pytest.mark.asyncio
async def test_openai_success_payload_cannot_echo_api_key() -> None:
    secret = "NONSTANDARD-OPENAI-SUCCESS-SECRET"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"x-request-id": f"request-{secret}"},
            json={
                "model": f"model-{secret}",
                "choices": [
                    {
                        "finish_reason": f"stop-{secret}",
                        "message": {"content": f"answer-{secret}"},
                    }
                ],
            },
        )

    result = await CompatibleModelClient(
        _settings("openai", secret=secret),
        transport=httpx.MockTransport(handler),
    ).ask(
        prompt="test",
        system_prompt=None,
        max_output_tokens=16,
        temperature=None,
    )

    assert secret not in result.model_dump_json()
    assert "[REDACTED]" in result.model_dump_json()


@pytest.mark.asyncio
async def test_anthropic_success_payload_cannot_echo_api_key() -> None:
    secret = "NONSTANDARD-ANTHROPIC-SUCCESS-SECRET"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": f"request-{secret}",
                "model": f"model-{secret}",
                "stop_reason": f"end-{secret}",
                "content": [
                    {"type": f"custom-{secret}"},
                    {"type": "text", "text": f"answer-{secret}"},
                ],
            },
        )

    result = await CompatibleModelClient(
        _settings("anthropic", secret=secret, auth_mode="x-api-key"),
        transport=httpx.MockTransport(handler),
    ).ask(
        prompt="test",
        system_prompt=None,
        max_output_tokens=16,
        temperature=None,
    )

    assert secret not in result.model_dump_json()
    assert "[REDACTED]" in result.model_dump_json()


@pytest.mark.asyncio
async def test_model_listing_cannot_echo_api_key() -> None:
    secret = "NONSTANDARD-MODEL-LIST-SECRET"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": f"model-{secret}"}]})

    models = await CompatibleModelClient(
        _settings("openai", secret=secret),
        transport=httpx.MockTransport(handler),
    ).list_models()

    assert secret not in json.dumps(models)
    assert "[REDACTED]" in models[0]


@pytest.mark.asyncio
async def test_http_client_ignores_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    real_async_client = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        captured["trust_env"] = kwargs.get("trust_env")
        return real_async_client(*args, **kwargs)

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    models = await CompatibleModelClient(
        _settings("openai"),
        transport=httpx.MockTransport(handler),
    ).list_models()

    assert models == []
    assert captured["trust_env"] is False


@pytest.mark.asyncio
async def test_redirect_does_not_forward_api_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            307,
            headers={"location": "https://unexpected.example/v1/models"},
            json={"error": {"message": "redirect refused"}},
        )

    with pytest.raises(ProviderError, match="HTTP 307"):
        await CompatibleModelClient(
            _settings("openai"),
            transport=httpx.MockTransport(handler),
        ).list_models()

    assert len(requests) == 1
    assert requests[0].url.host == "api.minimaxi.com"
