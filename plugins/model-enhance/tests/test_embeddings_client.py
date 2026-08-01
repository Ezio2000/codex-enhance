from __future__ import annotations

import json

import httpx
import pytest
from model_enhance_mcp.clients import CompatibleModelClient
from model_enhance_mcp.config import ProviderSettings
from model_enhance_mcp.constants import MAX_RESPONSE_BYTES
from model_enhance_mcp.errors import ProviderError
from pydantic import SecretStr


def _settings(*, secret: str = "embedding-secret") -> ProviderSettings:
    return ProviderSettings(
        protocol="openai",
        base_url="https://embedding.example/v1",
        api_key=SecretStr(secret),
        model="embed-model",
        auth_mode="bearer",
        vendor="generic",
        timeout_seconds=10,
    )


def _payload(*, count: int = 1, dimension: int = 3) -> dict[str, object]:
    return {
        "id": "provider-request",
        "model": "embed-model-v2",
        "data": [
            {"index": index, "embedding": [float(index + 1)] * dimension}
            for index in reversed(range(count))
        ],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


@pytest.mark.asyncio
async def test_embedding_request_and_dynamic_response_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://embedding.example/v1/embeddings"
        assert request.headers["authorization"] == "Bearer embedding-secret"
        assert json.loads(request.content) == {
            "model": "embed-model",
            "input": ["one", "two"],
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            headers={"x-request-id": "header-request"},
            json=_payload(count=2, dimension=3),
        )

    result = await CompatibleModelClient(
        _settings(), transport=httpx.MockTransport(handler)
    ).embed(["one", "two"])

    assert result.vectors == [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]
    assert result.model == "embed-model-v2"
    assert result.request_id == "provider-request"
    assert result.usage.input_tokens == 7
    assert result.usage.output_tokens is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        [{"index": 0, "embedding": []}],
        [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [1.0, 2.0]}],
        [{"index": 0, "embedding": [float("nan")]}],
        [{"index": 0, "embedding": [True]}],
        [{"index": 1, "embedding": [1.0]}],
    ],
)
async def test_rejects_invalid_embedding_vectors(data: list[dict[str, object]]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps({"data": data}, allow_nan=True).encode(),
        )

    client = CompatibleModelClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        await client.embed(["one"] * len(data))


@pytest.mark.asyncio
async def test_embedding_retries_transient_statuses() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json=_payload())

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = CompatibleModelClient(
        _settings(), transport=httpx.MockTransport(handler), sleep=sleep
    )
    await client.embed(["text"])

    assert attempts == 3
    assert delays == [0.0, 0.0]


@pytest.mark.asyncio
async def test_embedding_retries_timeouts_four_times() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = CompatibleModelClient(
        _settings(), transport=httpx.MockTransport(handler), sleep=sleep
    )
    with pytest.raises(ProviderError, match="timed out"):
        await client.embed(["text"])

    assert attempts == 4
    assert delays == [1, 2, 4]


@pytest.mark.asyncio
async def test_embedding_rejects_oversized_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))

    client = CompatibleModelClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="16 MiB"):
        await client.embed(["text"])


@pytest.mark.asyncio
async def test_embedding_errors_and_metadata_are_redacted() -> None:
    secret = "NONSTANDARD-EMBEDDING-SECRET"

    def failure(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": secret}})

    with pytest.raises(ProviderError) as caught:
        await CompatibleModelClient(
            _settings(secret=secret), transport=httpx.MockTransport(failure)
        ).embed(["text"])
    assert secret not in str(caught.value)

    def success(request: httpx.Request) -> httpx.Response:
        payload = _payload()
        payload["id"] = f"request-{secret}"
        payload["model"] = f"model-{secret}"
        return httpx.Response(200, json=payload)

    result = await CompatibleModelClient(
        _settings(secret=secret), transport=httpx.MockTransport(success)
    ).embed(["text"])
    assert secret not in repr(result)
    assert "[REDACTED]" in repr(result)
