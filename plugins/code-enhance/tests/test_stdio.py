from __future__ import annotations

import pytest

from code_enhance_mcp.server import mcp


@pytest.mark.asyncio
async def test_public_tool_surface_and_sensitive_boundaries() -> None:
    tools = await mcp.list_tools()
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {
        "embedding_config_status",
        "embed_inputs",
        "sync_code_index",
        "search_code_index",
    }
    assert "api_key" not in str(
        {name: tool.inputSchema for name, tool in by_name.items()}
    )
    assert (
        by_name["search_code_index"].inputSchema["properties"]["top_k"]["maximum"] == 50
    )
