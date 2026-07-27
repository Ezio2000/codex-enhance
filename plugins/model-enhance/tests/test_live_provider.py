from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _route_value(protocol: str, field: str) -> str | None:
    specific = os.environ.get(f"MODEL_ENHANCE_LIVE_{protocol.upper()}_{field}")
    return specific or os.environ.get(f"MODEL_ENHANCE_LIVE_{field}")


@pytest.mark.parametrize(
    ("protocol", "marker"),
    [
        ("openai", "CODE_7319_A"),
        ("anthropic", "CODE_7319_B"),
    ],
)
@pytest.mark.live
async def test_compatible_provider_live(
    protocol: str,
    marker: str,
    tmp_path: Path,
) -> None:
    if os.environ.get("MODEL_ENHANCE_RUN_LIVE_TESTS") != "1":
        pytest.skip("set MODEL_ENHANCE_RUN_LIVE_TESTS=1 to call a real provider")

    base_url = _route_value(protocol, "BASE_URL")
    api_key = _route_value(protocol, "API_KEY")
    model = _route_value(protocol, "MODEL")
    missing = [
        name
        for name, value in {
            "BASE_URL": base_url,
            "API_KEY": api_key,
            "MODEL": model,
        }.items()
        if not value
    ]
    if missing:
        pytest.skip(
            f"{protocol} live route is not configured: missing {', '.join(missing)}"
        )

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "model_enhance_mcp.server"],
        env=dict(os.environ),
    )
    with (tmp_path / "server.stderr").open("w+") as stderr:
        async with stdio_client(parameters, errlog=stderr) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "ask_model",
                    arguments={
                        "protocol": protocol,
                        "base_url": base_url,
                        "api_key": api_key,
                        "model": model,
                        "prompt": f"Output exactly {marker}. Do not explain.",
                        "system_prompt": (
                            "Return only the exact code requested by the user."
                        ),
                        "anthropic_auth_mode": os.environ.get(
                            "MODEL_ENHANCE_LIVE_ANTHROPIC_AUTH_MODE",
                            "x-api-key",
                        ),
                        "max_output_tokens": 64,
                        "temperature": 0.1,
                    },
                )

    assert result.isError is False
    assert result.structuredContent is not None
    assert marker in result.structuredContent["text"]
    assert result.structuredContent["protocol"] == protocol
    assert result.structuredContent["request_id"]
