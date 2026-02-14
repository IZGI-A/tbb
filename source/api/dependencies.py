"""FastAPI dependency injection for DB connections."""

import asyncpg
import redis.asyncio as aioredis
from clickhouse_driver import Client as CHClient

from config import settings
from db.postgres import get_pg_pool
from db.redis import get_redis


async def get_pg() -> asyncpg.Pool:
    return await get_pg_pool()


async def get_redis_client() -> aioredis.Redis:
    return await get_redis()


def get_ch() -> CHClient:
    return CHClient(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )
