"""Locked OpenAI-compatible Volcano Ark embedding client."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr

from .constants import (
    ARK_EMBEDDINGS_URL,
    ARK_MODEL,
    EMBEDDING_DIMENSION,
    MAX_RESPONSE_BYTES,
)
from .errors import ProviderError, redact
from .schemas import Usage

_RETRYABLE = frozenset({429, 502, 503, 504})


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    request_id: str | None
    usage: Usage


class ArkEmbeddingClient:
    """Call only the locked Coding Plan embeddings endpoint."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self._key = api_key.get_secret_value()
        self._transport = transport
        self._sleep = sleep

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            raise ProviderError("Embedding request must contain at least one input")
        body = {
            "model": ARK_MODEL,
            "input": texts,
            "encoding_format": "float",
        }
        response: httpx.Response | None = None
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(
                    timeout=60,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client:
                    request = client.build_request(
                        "POST",
                        ARK_EMBEDDINGS_URL,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self._key}",
                            "User-Agent": "code-enhance-mcp/0.3.0",
                        },
                        json=body,
                    )
                    response = await _send_bounded(client, request)
            except httpx.TimeoutException as exc:
                if attempt == 3:
                    raise ProviderError("Volcano Ark embeddings timed out") from exc
                await self._sleep(2**attempt)
                continue
            except httpx.HTTPError as exc:
                raise ProviderError(
                    f"Volcano Ark connection failed: {redact(str(exc), (self._key,))}"
                ) from exc

            if response.is_redirect:
                raise ProviderError(
                    f"Volcano Ark redirected HTTP {response.status_code}; "
                    "redirects are disabled",
                    status_code=response.status_code,
                )
            if response.status_code in _RETRYABLE and attempt < 3:
                await self._sleep(_retry_delay(response, attempt))
                continue
            break

        if response is None:
            raise ProviderError("Volcano Ark returned no response")
        if response.status_code >= 400:
            preview = redact(response.text[:1000], (self._key,))
            raise ProviderError(
                f"Volcano Ark returned HTTP {response.status_code}: {preview}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderError("Volcano Ark returned non-JSON content") from exc
        vectors = _parse_vectors(payload, expected=len(texts))
        usage_raw = payload.get("usage")
        usage = Usage(
            prompt_tokens=_safe_nonnegative_int(usage_raw, "prompt_tokens"),
            total_tokens=_safe_nonnegative_int(usage_raw, "total_tokens"),
        )
        request_id = _safe_string(
            response.headers.get("x-request-id")
            or payload.get("id")
            or payload.get("request_id"),
            secret=self._key,
        )
        return EmbeddingBatch(vectors=vectors, request_id=request_id, usage=usage)


async def _send_bounded(
    client: httpx.AsyncClient,
    request: httpx.Request,
) -> httpx.Response:
    response = await client.send(request, stream=True)
    chunks: list[bytes] = []
    size = 0
    try:
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ProviderError("Volcano Ark response exceeded the 16 MiB limit")
            chunks.append(chunk)
    finally:
        await response.aclose()
    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=b"".join(chunks),
        request=request,
    )


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("retry-after")
    if raw:
        try:
            return min(max(float(raw), 0), 10)
        except ValueError:
            pass
    return float(2**attempt)


def _parse_vectors(payload: object, *, expected: int) -> list[list[float]]:
    if not isinstance(payload, dict):
        raise ProviderError("Volcano Ark response must be a JSON object")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected:
        raise ProviderError(
            "Volcano Ark response data count does not match the request"
        )
    ordered: list[tuple[int, list[float]]] = []
    for fallback, item in enumerate(data):
        if not isinstance(item, dict):
            raise ProviderError("Volcano Ark response contains an invalid data item")
        index = item.get("index", fallback)
        vector = item.get("embedding")
        if not isinstance(index, int) or not isinstance(vector, list):
            raise ProviderError("Volcano Ark response contains an invalid embedding")
        if len(vector) != EMBEDDING_DIMENSION:
            raise ProviderError(
                f"Expected {EMBEDDING_DIMENSION} dimensions, got {len(vector)}"
            )
        converted: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProviderError("Embedding contains a non-numeric value")
            number = float(value)
            if not math.isfinite(number):
                raise ProviderError("Embedding contains NaN or infinity")
            converted.append(number)
        ordered.append((index, converted))
    ordered.sort(key=lambda pair: pair[0])
    if [index for index, _ in ordered] != list(range(expected)):
        raise ProviderError("Embedding indexes are missing or duplicated")
    return [vector for _, vector in ordered]


def _safe_nonnegative_int(value: object, key: str) -> int | None:
    if not isinstance(value, dict):
        return None
    result = value.get(key)
    return (
        result
        if isinstance(result, int) and not isinstance(result, bool) and result >= 0
        else None
    )


def _safe_string(value: object, *, secret: str) -> str | None:
    return redact(value, (secret,))[:500] if isinstance(value, str) and value else None
