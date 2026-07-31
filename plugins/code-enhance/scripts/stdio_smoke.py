"""List and validate the Code Enhance MCP tool surface."""

from __future__ import annotations

import argparse
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def list_tools() -> None:
    parameters = StdioServerParameters(
        command="uv",
        args=["run", "--locked", "--no-dev", "code-enhance-mcp"],
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        expected = {
            "embedding_config_status",
            "embed_inputs",
            "sync_code_index",
            "search_code_index",
        }
        if set(names) != expected:
            raise RuntimeError(f"Unexpected Code Enhance tools: {names}")
        print("\n".join(sorted(names)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-tools", action="store_true")
    arguments = parser.parse_args()
    if not arguments.list_tools:
        parser.error("--list-tools is required")
    asyncio.run(list_tools())


if __name__ == "__main__":
    main()
