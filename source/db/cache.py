"""Centralized Redis cache helpers with gzip compression."""

import gzip
import json
import base64
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_COMPRESS_LEVEL = 6
_MIN_COMPRESS_SIZE = 256


async def cache_get(redis: aioredis.Redis, key: str) -> Any | None:
    raw: str | None = await redis.get(key)
    if raw is None:
        return None

    if raw.startswith("H4sI"):
        try:
            compressed = base64.b64decode(raw)
            decompressed = gzip.decompress(compressed)
            return json.loads(decompressed)
        except Exception:
            logger.warning("Failed to decompress cache key %s, treating as raw JSON", key)

    return json.loads(raw)


async def cache_set(
    redis: aioredis.Redis,
    key: str,
    data: Any,
    ttl: int,
    *,
    default: Any = None,
) -> None:
    json_str = json.dumps(data, default=default)

    if len(json_str) >= _MIN_COMPRESS_SIZE:
        compressed = gzip.compress(json_str.encode("utf-8"), compresslevel=_COMPRESS_LEVEL)
        encoded = base64.b64encode(compressed).decode("ascii")
        await redis.setex(key, ttl, encoded)
    else:
        await redis.setex(key, ttl, json_str)
