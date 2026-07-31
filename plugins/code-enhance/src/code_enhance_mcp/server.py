"""STDIO MCP entry point and public tools."""

from __future__ import annotations

import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from .config import configuration_status, load_settings
from .indexing import search_index, sync_index
from .schemas import (
    EmbedArtifactResult,
    EmbedInput,
    IndexSearchResult,
    IndexSyncResult,
)
from .service import embed_to_artifact

mcp = FastMCP(
    "Code Enhance",
    instructions=(
        "The embed and index tools send explicitly selected text to the locked "
        "Volcano Ark Coding Plan endpoint and may consume plan quota. They load "
        "the API key only from the private Code Enhance config file, never "
        "return it, and write artifacts/indexes only below the external cache "
        "root. Existing Code Enhance review skills do not invoke these tools."
    ),
)


def _result(model: object, *, text: str | None = None) -> CallToolResult:
    structured = model.model_dump(mode="json")  # type: ignore[attr-defined]
    serialized = json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
    return CallToolResult(
        content=[TextContent(type="text", text=text or serialized)],
        structuredContent=structured,
    )


@mcp.tool(
    title="Check Code Enhance embedding configuration",
    description=(
        "Check whether the private Volcano Ark Coding Plan configuration is "
        "ready without returning or transmitting the API key."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def embedding_config_status() -> CallToolResult:
    structured = configuration_status()
    serialized = json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
    return CallToolResult(
        content=[TextContent(type="text", text=serialized)],
        structuredContent=structured,
    )


@mcp.tool(
    title="Embed selected text or repository files",
    description=(
        "Send explicitly selected text or repository-local UTF-8 files to the "
        "locked Volcano Ark Coding Plan embedding endpoint. Save complete "
        "1024-dimensional vectors as a JSON artifact outside the repository."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def embed_inputs(
    items: Annotated[
        list[EmbedInput],
        Field(min_length=1, max_length=64),
    ],
    repository: Annotated[
        str | None,
        Field(
            default=None,
            max_length=4096,
            description="Git repository root, required when any item uses path.",
        ),
    ] = None,
) -> Annotated[CallToolResult, EmbedArtifactResult]:
    result = await embed_to_artifact(
        load_settings(),
        items,
        repository=repository,
    )
    return _result(
        result,
        text=(
            f"Saved {result.count} {result.dimension}-dimensional embeddings "
            f"to {result.artifact_path}"
        ),
    )


@mcp.tool(
    title="Synchronize a semantic code index",
    description=(
        "Resolve a repository or directory with the shared Code Enhance scope "
        "helper, send changed safe text chunks to Volcano Ark, and atomically "
        "update the external SQLite index. Unchanged chunks are not resent."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def sync_code_index(
    repository: Annotated[str, Field(min_length=1, max_length=4096)],
    path: Annotated[str | None, Field(default=None, max_length=4096)] = None,
    rebuild: Annotated[bool, Field(default=False)] = False,
) -> Annotated[CallToolResult, IndexSyncResult]:
    result = await sync_index(
        load_settings(),
        repository,
        path=path,
        rebuild=rebuild,
    )
    return _result(result)


@mcp.tool(
    title="Search a semantic code index",
    description=(
        "Embed one natural-language query with Volcano Ark and cosine-rank the "
        "existing local code index. Return only current hash-verified source "
        "paths, line ranges, scores, and bounded previews."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def search_code_index(
    repository: Annotated[str, Field(min_length=1, max_length=4096)],
    query: Annotated[str, Field(min_length=1, max_length=20_000)],
    path: Annotated[str | None, Field(default=None, max_length=4096)] = None,
    top_k: Annotated[int, Field(default=10, ge=1, le=50)] = 10,
) -> Annotated[CallToolResult, IndexSearchResult]:
    result = await search_index(
        load_settings(),
        repository,
        query,
        path=path,
        top_k=top_k,
    )
    return _result(result)


def main() -> None:
    """Run only the local stdio transport."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
