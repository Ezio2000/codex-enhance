"""Low-level MiniMax Files and OpenAI-compatible chat transport."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import httpx
from pydantic import SecretStr

from ...errors import ProviderError, redact


@dataclass(slots=True)
class UploadedFile:
    file_id: str
    cleanup_warning: str | None = None


@dataclass(frozen=True, slots=True)
class CompletionResult:
    content: str
    finish_reason: str | None
    usage: dict[str, Any]
    latency_ms: int
    structured_via_tool: bool


def analysis_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_video_analysis",
            "description": (
                "Submit the final video analysis. Call exactly once after inspecting "
                "the video. Put the complete compact JSON object in payload."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "payload": {
                        "type": "string",
                        "description": (
                            "Compact JSON object with summary, answer, timeline, "
                            "observations, and uncertainties. No XML or Markdown."
                        ),
                    }
                },
                "required": ["payload"],
            },
        },
    }


def tool_arguments_content(arguments: Any) -> str | None:
    """Unwrap MiniMax's documented JSON-string arguments or an SDK-decoded dict."""

    decoded = arguments
    if isinstance(arguments, str):
        try:
            decoded = json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
    if isinstance(decoded, dict):
        payload = decoded.get("payload")
        if isinstance(payload, str):
            return payload
        return json.dumps(decoded, ensure_ascii=False)
    return arguments if isinstance(arguments, str) else None


class MiniMaxClient:
    def __init__(self, *, base_url: str, api_key: SecretStr) -> None:
        self.base_url = base_url.rstrip("/")
        self._secret = api_key.get_secret_value()
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._secret}"},
            timeout=httpx.Timeout(360.0, connect=30.0),
            follow_redirects=False,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    def _checked_payload(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_redirect:
            raise ProviderError(
                f"MiniMax refused HTTP redirect {response.status_code}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            preview = redact(response.text, self._secret)[:1000]
            raise ProviderError(
                f"MiniMax returned non-JSON HTTP {response.status_code}: {preview}",
                status_code=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderError(
                "MiniMax returned an unexpected payload",
                status_code=response.status_code,
            )
        base_resp = payload.get("base_resp")
        app_error = isinstance(base_resp, dict) and base_resp.get("status_code", 0) != 0
        if response.is_error or app_error:
            serialized = json.dumps(payload, ensure_ascii=False)
            preview = redact(serialized, self._secret)[:2000]
            raise ProviderError(
                f"MiniMax request failed (HTTP {response.status_code}): {preview}",
                status_code=response.status_code,
            )
        return payload

    async def upload_video(self, video_path: Path) -> UploadedFile:
        try:
            with video_path.open("rb") as handle:
                response = await self._client.post(
                    f"{self.base_url}/files/upload",
                    data={"purpose": "video_understanding"},
                    files={"file": (video_path.name, handle, "video/mp4")},
                )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"MiniMax video upload failed: {redact(str(exc), self._secret)}"
            ) from exc
        payload = self._checked_payload(response)
        file_data = payload.get("file")
        file_id = file_data.get("file_id") if isinstance(file_data, dict) else None
        if file_id is None or not str(file_id):
            raise ProviderError("MiniMax upload response did not include file.file_id")
        return UploadedFile(file_id=str(file_id))

    async def delete_video(self, file_id: str) -> None:
        try:
            response = await self._client.post(
                f"{self.base_url}/files/delete",
                files={
                    "file_id": (None, file_id),
                    "purpose": (None, "video_understanding"),
                },
                timeout=60,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"MiniMax temporary-file cleanup failed: {redact(str(exc), self._secret)}"
            ) from exc
        self._checked_payload(response)

    @asynccontextmanager
    async def temporary_upload(
        self, video_path: Path, *, delete_remote: bool
    ) -> AsyncIterator[UploadedFile]:
        uploaded = await self.upload_video(video_path)
        primary_error: Exception | None = None
        try:
            yield uploaded
        except Exception as exc:
            # Capture the primary failure so a cleanup failure or configured
            # retention policy cannot make remote-file risk disappear.
            primary_error = exc
            raise
        finally:
            if not delete_remote:
                uploaded.cleanup_warning = (
                    "Remote upload was retained because "
                    "security.delete_remote_files=false"
                )
            else:
                try:
                    await asyncio.shield(self.delete_video(uploaded.file_id))
                except Exception as exc:  # noqa: BLE001
                    # Cleanup is best-effort, including for unexpected provider
                    # failures, but the warning must remain safe to expose.
                    uploaded.cleanup_warning = redact(str(exc), self._secret)[:1000]
                    uploaded.cleanup_warning = (
                        "Remote cleanup failed and the uploaded file may remain: "
                        + uploaded.cleanup_warning
                    )

            if primary_error is not None and uploaded.cleanup_warning:
                primary_preview = redact(str(primary_error), self._secret)[:1000]
                status_code = (
                    primary_error.status_code
                    if isinstance(primary_error, ProviderError)
                    else None
                )
                raise ProviderError(
                    f"{primary_preview}; {uploaded.cleanup_warning}",
                    status_code=status_code,
                ) from primary_error

    async def analyze_video(
        self,
        file_id: str,
        *,
        model: str,
        prompt: str,
        detail: str,
        fps: float,
        max_completion_tokens: int,
    ) -> CompletionResult:
        request: dict[str, Any] = {
            "model": model,
            "thinking": {"type": "disabled"},
            "reasoning_split": True,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                            + "\n必须调用 `submit_video_analysis` 工具一次。将上述完整 JSON 对象"
                            "序列化为一个字符串，放进唯一的 payload 参数；不要使用 XML，不要在正文重复。",
                        },
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": f"mm_file://{file_id}",
                                "detail": detail,
                                "fps": fps,
                            },
                        },
                    ],
                }
            ],
            "max_completion_tokens": max_completion_tokens,
            "temperature": 0.1,
            "tools": [analysis_tool_definition()],
            "tool_choice": "auto",
        }
        started = time.perf_counter()
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions", json=request
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"MiniMax video analysis failed: {redact(str(exc), self._secret)}"
            ) from exc
        latency_ms = round((time.perf_counter() - started) * 1000)
        payload = self._checked_payload(response)
        choices = payload.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise ProviderError("MiniMax response did not include a completion choice")
        choice = choices[0]
        message = choice.get("message")
        content: Any = message.get("content") if isinstance(message, dict) else None
        structured = False
        tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if isinstance(tool_calls, list):
            for call in tool_calls:
                function = call.get("function") if isinstance(call, dict) else None
                if (
                    not isinstance(function, dict)
                    or function.get("name") != "submit_video_analysis"
                ):
                    continue
                arguments = function.get("arguments")
                content = tool_arguments_content(arguments)
                if isinstance(content, str):
                    structured = True
                    break
        if isinstance(content, list):
            content = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("MiniMax response did not contain text content")
        usage = payload.get("usage")
        return CompletionResult(
            content=content,
            finish_reason=choice.get("finish_reason"),
            usage=usage if isinstance(usage, dict) else {},
            latency_ms=latency_ms,
            structured_via_tool=structured,
        )
