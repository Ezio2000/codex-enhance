"""Locked provider and index contracts."""

from __future__ import annotations

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_EMBEDDINGS_URL = f"{ARK_BASE_URL}/embeddings"
ARK_MODEL = "doubao-embedding-vision"
EMBEDDING_DIMENSION = 1024

CONFIG_VERSION = 1
INDEX_SCHEMA_VERSION = 1
CHUNKER_VERSION = "line-v1"

MAX_ITEMS = 64
MAX_ITEM_CHARS = 100_000
MAX_TOTAL_CHARS = 1_000_000
MAX_FILE_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
BATCH_SIZE = 16

TARGET_CHARS = 4_000
MAX_CHARS = 8_000
MAX_LINES = 200
OVERLAP_LINES = 20
