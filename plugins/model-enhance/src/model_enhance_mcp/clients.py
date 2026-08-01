"""Protocol adapters for non-streaming compatible model calls."""

from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import ProviderSettings
from .constants import MAX_RESPONSE_BYTES
from .errors import ProviderError, redact
from .schemas import ModelResult, Usage

_LEADING_THINKING = re.compile(r"^\s*(?:<think>.*?</think>\s*)+", re.DOTALL)
_RETRYABLE = frozenset({429, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    model: str
    request_id: str | None
    usage: Usage


class CompatibleModelClient:
    """Call one caller-supplied OpenAI- or Anthropic-compatible provider."""

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._sleep = sleep

    async def ask(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        max_output_tokens: int,
        temperature: float | None,
    ) -> ModelResult:
        selected_model = self.settings.model
        if self.settings.protocol == "openai":
            return await self._ask_openai(
                prompt=prompt,
                system_prompt=system_prompt,
                model=selected_model,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        return await self._ask_anthropic(
            prompt=prompt,
            system_prompt=system_prompt,
            model=selected_model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    async def list_models(self) -> list[str]:
        suffix = "/models" if self.settings.protocol == "openai" else "/v1/models"
        payload, _ = await self._request("GET", f"{self.settings.base_url}{suffix}")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ProviderError(
                f"{self.settings.protocol} model list has no data array"
            )
        key = self.settings.api_key.get_secret_value()
        models = {
            redact(item["id"], (key,))
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        return sorted(models)

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        if self.settings.protocol != "openai":
            raise ProviderError("Embeddings require the OpenAI-compatible protocol")
        if not texts:
            raise ProviderError("Embedding request must contain at least one input")
        payload, response = await self._request(
            "POST",
            f"{self.settings.base_url}/embeddings",
            json_body={
                "model": self.settings.model,
                "input": texts,
                "encoding_format": "float",
            },
            retry_transient=True,
            max_response_bytes=MAX_RESPONSE_BYTES,
        )
        key = self.settings.api_key.get_secret_value()
        return EmbeddingBatch(
            vectors=_embedding_vectors(payload, expected=len(texts)),
            model=(
                _safe_optional_string(payload.get("model"), key)
                or redact(self.settings.model, (key,))
            ),
            request_id=_safe_optional_string(_request_id(payload, response), key),
            usage=_usage_from_openai(payload.get("usage")),
        )

    async def _ask_openai(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        model: str,
        max_output_tokens: int,
        temperature: float | None,
    ) -> ModelResult:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if self.settings.vendor == "minimax":
            request.update(
                {
                    "max_completion_tokens": max_output_tokens,
                    "thinking": {"type": "disabled"},
                    "reasoning_split": True,
                }
            )
        else:
            request["max_tokens"] = max_output_tokens
        if temperature is not None:
            request["temperature"] = temperature

        payload, response = await self._request(
            "POST",
            f"{self.settings.base_url}/chat/completions",
            json_body=request,
        )
        choices = payload.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise ProviderError("OpenAI-compatible response has no choices")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ProviderError("OpenAI-compatible response has no assistant message")

        key = self.settings.api_key.get_secret_value()
        text = _openai_text(message.get("content"))
        text = redact(_LEADING_THINKING.sub("", text).strip(), (key,))
        if not text:
            raise ProviderError("OpenAI-compatible response contains no final text")
        usage = _usage_from_openai(payload.get("usage"))
        request_id = _safe_optional_string(_request_id(payload, response), key)
        actual_model = _safe_optional_string(payload.get("model"), key) or redact(
            model, (key,)
        )
        warnings: list[str] = []
        if message.get("tool_calls"):
            warnings.append(
                "Upstream tool calls were ignored; this MCP only returns final text"
            )
        return ModelResult(
            protocol="openai",
            model=actual_model,
            text=text,
            finish_reason=_safe_optional_string(choice.get("finish_reason"), key),
            request_id=request_id,
            usage=usage,
            warnings=warnings,
        )

    async def _ask_anthropic(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        model: str,
        max_output_tokens: int,
        temperature: float | None,
    ) -> ModelResult:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if system_prompt:
            request["system"] = system_prompt
        if temperature is not None:
            request["temperature"] = temperature
        if self.settings.vendor == "minimax":
            request["thinking"] = {"type": "disabled"}

        payload, response = await self._request(
            "POST",
            f"{self.settings.base_url}/v1/messages",
            json_body=request,
        )
        blocks = payload.get("content")
        if not isinstance(blocks, list):
            raise ProviderError("Anthropic-compatible response has no content blocks")
        text_parts: list[str] = []
        ignored: set[str] = set()
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif isinstance(block_type, str):
                ignored.add(block_type)
        key = self.settings.api_key.get_secret_value()
        text = redact("\n".join(part for part in text_parts if part).strip(), (key,))
        if not text:
            raise ProviderError("Anthropic-compatible response contains no final text")
        warnings = (
            [
                "Ignored non-text Anthropic blocks: "
                + redact(", ".join(sorted(ignored)), (key,))
            ]
            if ignored - {"thinking", "redacted_thinking"}
            else []
        )
        return ModelResult(
            protocol="anthropic",
            model=(
                _safe_optional_string(payload.get("model"), key)
                or redact(model, (key,))
            ),
            text=text,
            finish_reason=_safe_optional_string(payload.get("stop_reason"), key),
            request_id=_safe_optional_string(_request_id(payload, response), key),
            usage=_usage_from_anthropic(payload.get("usage")),
            warnings=warnings,
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        retry_transient: bool = False,
        max_response_bytes: int | None = None,
    ) -> tuple[dict[str, Any], httpx.Response]:
        key = self.settings.api_key.get_secret_value()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "model-enhance-mcp/0.2.0",
        }
        if self.settings.protocol == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
        if self.settings.protocol == "openai" or self.settings.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        else:
            headers["x-api-key"] = key

        attempts = 4 if retry_transient else 1
        response: httpx.Response | None = None
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client:
                    response = await client.request(
                        method, url, headers=headers, json=json_body
                    )
            except httpx.TimeoutException as exc:
                if attempt + 1 < attempts:
                    await self._sleep(2**attempt)
                    continue
                raise ProviderError(
                    f"{self.settings.protocol} provider timed out after "
                    f"{self.settings.timeout_seconds:g}s"
                ) from exc
            except httpx.HTTPError as exc:
                detail = redact(str(exc), (key,))
                raise ProviderError(
                    f"{self.settings.protocol} provider connection failed: {detail}"
                ) from exc
            if response.status_code in _RETRYABLE and attempt + 1 < attempts:
                await self._sleep(_retry_delay(response, attempt))
                continue
            break

        if response is None:
            raise ProviderError(
                f"{self.settings.protocol} provider returned no response"
            )

        if response.is_redirect:
            raise ProviderError(
                f"{self.settings.protocol} provider redirected HTTP "
                f"{response.status_code}; redirects are disabled",
                status_code=response.status_code,
            )
        if (
            max_response_bytes is not None
            and len(response.content) > max_response_bytes
        ):
            raise ProviderError(
                f"{self.settings.protocol} provider response exceeded the "
                f"{max_response_bytes // (1024 * 1024)} MiB limit"
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"{self.settings.protocol} provider returned non-JSON HTTP "
                f"{response.status_code}",
                status_code=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderError(
                f"{self.settings.protocol} provider returned a non-object "
                "JSON response",
                status_code=response.status_code,
            )
        if response.is_error:
            detail = _safe_error_detail(payload, key)
            raise ProviderError(
                f"{self.settings.protocol} provider returned HTTP "
                f"{response.status_code}: {detail}",
                status_code=response.status_code,
            )
        base_resp = payload.get("base_resp")
        if (
            isinstance(base_resp, dict)
            and isinstance(base_resp.get("status_code"), int)
            and base_resp["status_code"] != 0
        ):
            detail = _safe_error_detail(payload, key)
            raise ProviderError(
                f"{self.settings.protocol} provider rejected the request: {detail}"
            )
        return payload, response


def _openai_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def _embedding_vectors(payload: dict[str, Any], *, expected: int) -> list[list[float]]:
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected:
        raise ProviderError(
            "OpenAI-compatible embedding data count does not match the request"
        )
    ordered: list[tuple[int, list[float]]] = []
    dimension: int | None = None
    for fallback, item in enumerate(data):
        if not isinstance(item, dict):
            raise ProviderError("Embedding response contains an invalid data item")
        index = item.get("index", fallback)
        vector = item.get("embedding")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not isinstance(vector, list)
        ):
            raise ProviderError("Embedding response contains an invalid vector")
        if not vector:
            raise ProviderError("Embedding vectors must not be empty")
        converted: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProviderError("Embedding contains a non-numeric value")
            number = float(value)
            if not math.isfinite(number):
                raise ProviderError("Embedding contains NaN or infinity")
            converted.append(number)
        if dimension is not None and dimension != len(converted):
            raise ProviderError("Embedding response contains inconsistent dimensions")
        dimension = len(converted)
        ordered.append((index, converted))
    ordered.sort(key=lambda pair: pair[0])
    if [index for index, _ in ordered] != list(range(expected)):
        raise ProviderError("Embedding indexes are missing or duplicated")
    return [vector for _, vector in ordered]


def _usage_from_openai(value: Any) -> Usage:
    if not isinstance(value, dict):
        return Usage()
    return Usage(
        input_tokens=_optional_int(value.get("prompt_tokens")),
        output_tokens=_optional_int(value.get("completion_tokens")),
        total_tokens=_optional_int(value.get("total_tokens")),
    )


def _usage_from_anthropic(value: Any) -> Usage:
    if not isinstance(value, dict):
        return Usage()
    input_tokens = _optional_int(value.get("input_tokens"))
    output_tokens = _optional_int(value.get("output_tokens"))
    total_tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _request_id(payload: dict[str, Any], response: httpx.Response) -> str | None:
    payload_id = payload.get("id")
    if isinstance(payload_id, str):
        return payload_id
    return response.headers.get("x-request-id") or response.headers.get("request-id")


def _safe_error_detail(payload: dict[str, Any], key: str) -> str:
    candidate: Any = payload.get("error") or payload.get("base_resp") or payload
    if isinstance(candidate, dict):
        message = candidate.get("message") or candidate.get("status_msg") or candidate
    else:
        message = candidate
    if not isinstance(message, str):
        message = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    # Redact before truncating so a secret that crosses the truncation boundary
    # cannot leak as an otherwise-unrecognizable prefix.
    return redact(message, (key,))[:1000]


def _optional_int(value: Any) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _safe_optional_string(value: Any, key: str) -> str | None:
    return redact(value, (key,)) if isinstance(value, str) else None


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("retry-after")
    if raw:
        try:
            return min(max(float(raw), 0), 10)
        except ValueError:
            pass
    return float(2**attempt)
