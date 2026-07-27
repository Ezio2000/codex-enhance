from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_stdio_server_exposes_expected_tools(tmp_path: Path) -> None:
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
                result = await session.list_tools()
                missing_key = await session.call_tool(
                    "ask_model",
                    arguments={
                        "protocol": "openai",
                        "base_url": "https://router.example/v1",
                        "model": "test-model",
                        "prompt": "test",
                    },
                )
                blank_prompt = await session.call_tool(
                    "ask_model",
                    arguments={
                        "protocol": "openai",
                        "base_url": "https://router.example/v1",
                        "api_key": "sensitive-test-key",
                        "model": "test-model",
                        "prompt": "   ",
                    },
                )
                oversized_key = (
                    "BEGIN_OVERSIZED_SECRET_" + "x" * 4096 + "_END_OVERSIZED_SECRET"
                )
                oversized_ask = await session.call_tool(
                    "ask_model",
                    arguments={
                        "protocol": "openai",
                        "base_url": "https://router.example/v1",
                        "api_key": oversized_key,
                        "model": "test-model",
                        "prompt": "test",
                    },
                )
                oversized_list = await session.call_tool(
                    "list_models",
                    arguments={
                        "protocol": "openai",
                        "base_url": "https://router.example/v1",
                        "api_key": oversized_key,
                    },
                )

    tools = {tool.name: tool for tool in result.tools}
    assert set(tools) == {"ask_model", "list_models"}
    assert tools["ask_model"].annotations is not None
    assert tools["ask_model"].annotations.openWorldHint is True
    assert tools["ask_model"].annotations.readOnlyHint is False
    assert tools["list_models"].annotations is not None
    assert tools["list_models"].annotations.readOnlyHint is False
    ask_schema = tools["ask_model"].inputSchema
    assert set(ask_schema["required"]) >= {
        "protocol",
        "base_url",
        "api_key",
        "model",
        "prompt",
    }
    assert ask_schema["properties"]["api_key"]["writeOnly"] is True
    assert set(tools["list_models"].inputSchema["required"]) >= {
        "protocol",
        "base_url",
        "api_key",
    }
    assert tools["ask_model"].outputSchema is not None
    assert "text" in tools["ask_model"].outputSchema.get("properties", {})
    assert tools["list_models"].outputSchema is not None
    assert "models" in tools["list_models"].outputSchema.get("properties", {})
    assert missing_key.isError is True
    assert blank_prompt.isError is True
    assert "sensitive-test-key" not in str(blank_prompt)
    for failure in (oversized_ask, oversized_list):
        assert failure.isError is True
        assert "BEGIN_OVERSIZED_SECRET_" not in str(failure)
        assert "END_OVERSIZED_SECRET" not in str(failure)
