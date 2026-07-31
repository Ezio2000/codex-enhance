from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from code_enhance_mcp.client import ArkEmbeddingClient
from code_enhance_mcp.constants import (
    ARK_EMBEDDINGS_URL,
    ARK_MODEL,
    EMBEDDING_DIMENSION,
    MAX_RESPONSE_BYTES,
)
from code_enhance_mcp.errors import ProviderError


def _payload(count: int = 1) -> dict[str, object]:
    return {
        "id": "provider-request",
        "data": [
            {
                "object": "embedding",
                "index": index,
                "embedding": [float(index + 1)] * EMBEDDING_DIMENSION,
            }
            for index in range(count)
        ],
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }


@pytest.mark.asyncio
async def test_calls_only_locked_openai_compatible_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ARK_EMBEDDINGS_URL
        assert request.headers["authorization"] == "Bearer private-key"
        body = json.loads(request.content)
        assert body == {
            "model": ARK_MODEL,
            "input": ["one", "two"],
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            headers={"x-request-id": "header-request"},
            json=_payload(2),
        )

    client = ArkEmbeddingClient(
        SecretStr("private-key"),
        transport=httpx.MockTransport(handler),
    )
    result = await client.embed(["one", "two"])

    assert len(result.vectors) == 2
    assert result.request_id == "header-request"
    assert result.usage.total_tokens == 3


@pytest.mark.asyncio
async def test_rejects_redirect_without_forwarding_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": "https://evil.example/"})

    client = ArkEmbeddingClient(
        SecretStr("never-forward-this"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError, match="redirect"):
        await client.embed(["text"])


@pytest.mark.asyncio
async def test_retries_rate_limit_with_bounded_delay() -> None:
    attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json=_payload())

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = ArkEmbeddingClient(
        SecretStr("private-key"),
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    await client.embed(["text"])

    assert attempts == 3
    assert delays == [0.0, 0.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedding",
    [
        [0.0] * (EMBEDDING_DIMENSION - 1),
        [0.0] * (EMBEDDING_DIMENSION - 1) + [float("nan")],
        ["bad"] * EMBEDDING_DIMENSION,
    ],
)
async def test_rejects_invalid_vectors(embedding: list[object]) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(
                {"data": [{"index": 0, "embedding": embedding}]},
                allow_nan=True,
            ).encode(),
        )

    client = ArkEmbeddingClient(
        SecretStr("private-key"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError):
        await client.embed(["text"])


@pytest.mark.asyncio
async def test_provider_error_redacts_api_key() -> None:
    secret = "AKLT-SUPER-SENSITIVE-KEY"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            text=f"Authorization: Bearer {secret}",
        )

    client = ArkEmbeddingClient(
        SecretStr(secret),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError) as caught:
        await client.embed(["text"])

    assert secret not in str(caught.value)


@pytest.mark.asyncio
async def test_request_id_is_bounded_and_redacted() -> None:
    secret = "AKLT-SUPER-SENSITIVE-KEY"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"x-request-id": f"request-{secret}"},
            json=_payload(),
        )

    client = ArkEmbeddingClient(
        SecretStr(secret),
        transport=httpx.MockTransport(handler),
    )
    result = await client.embed(["text"])

    assert result.request_id is not None
    assert secret not in result.request_id
    assert "[REDACTED]" in result.request_id


@pytest.mark.asyncio
async def test_retries_timeouts_and_stops_after_four_attempts() -> None:
    attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = ArkEmbeddingClient(
        SecretStr("private-key"),
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    with pytest.raises(ProviderError, match="timed out"):
        await client.embed(["text"])

    assert attempts == 4
    assert delays == [1, 2, 4]


@pytest.mark.asyncio
async def test_rejects_oversized_response_before_json_parsing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))

    client = ArkEmbeddingClient(
        SecretStr("private-key"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError, match="16 MiB"):
        await client.embed(["text"])
