#!/usr/bin/env python3
"""Exercise the packaged server through a real MCP stdio session."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


async def run(*, list_tools: bool) -> None:
    server = StdioServerParameters(
        command="uv",
        args=["run", "--locked", "--no-dev", "model-enhance-mcp"],
        cwd=PLUGIN_ROOT,
    )
    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = {item.name for item in tools.tools}
        expected = {"ask_model", "list_models"}
        if names != expected:
            expected_names = sorted(expected)
            actual_names = sorted(names)
            raise RuntimeError(
                f"unexpected tool set: expected {expected_names}, got {actual_names}"
            )
        for item in tools.tools:
            if item.annotations is None or item.annotations.readOnlyHint is not False:
                raise RuntimeError(f"{item.name} must require approval")
            api_key_schema = item.inputSchema["properties"]["api_key"]
            if api_key_schema.get("writeOnly") is not True:
                raise RuntimeError(f"{item.name}.api_key must be writeOnly")
        if list_tools:
            print(
                json.dumps(
                    [
                        {
                            "name": item.name,
                            "inputSchema": item.inputSchema,
                            "outputSchema": item.outputSchema,
                            "annotations": (
                                item.annotations.model_dump(mode="json")
                                if item.annotations is not None
                                else None
                            ),
                        }
                        for item in tools.tools
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-tools", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(list_tools=args.list_tools))


if __name__ == "__main__":
    main()
