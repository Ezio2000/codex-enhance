#!/usr/bin/env python3
"""Exercise the plugin through a real MCP stdio session."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


async def run(args: argparse.Namespace) -> None:
    server = StdioServerParameters(
        command="uv",
        args=[
            "--directory",
            str(PLUGIN_ROOT),
            "run",
            "--locked",
            "--no-dev",
            "video-enhance-mcp",
        ],
    )
    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        if args.list_tools:
            tools = await session.list_tools()
            print(
                json.dumps(
                    [
                        {
                            "name": item.name,
                            "inputSchema": item.inputSchema,
                            "outputSchema": item.outputSchema,
                        }
                        for item in tools.tools
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        name = "video_analyze" if args.analyze else "video_inspect"
        arguments: dict[str, object] = {"video_path": args.video}
        if args.analyze:
            arguments.update(
                operation=args.operation,
                prompt=args.prompt,
                profile=args.profile,
                provider=args.provider,
            )
        result = await session.call_tool(name, arguments)
        payload = result.structuredContent
        if payload is None:
            payload = [content.model_dump() for content in result.content]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if result.isError:
            raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--video", default="")
    parser.add_argument("--operation", default="summary")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--profile", default="auto")
    parser.add_argument("--provider", default="auto")
    args = parser.parse_args()
    if not args.list_tools and not args.video:
        parser.error("--video is required unless --list-tools is used")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
