"""Bank information service - queries PostgreSQL."""

import logging

import asyncpg
import redis.asyncio as aioredis

from db.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 hours


async def get_banks(pool: asyncpg.Pool, redis: aioredis.Redis) -> list[dict]:
    cache_key = "banks:list"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bank_info ORDER BY bank_name"
        )

    data = [dict(r) for r in rows]
    # Convert datetime objects to strings for JSON serialization
    for d in data:
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_branches(
    pool: asyncpg.Pool,
    redis: aioredis.Redis,
    bank_name: str,
    city: str | None = None,
) -> list[dict]:
    cache_key = f"banks:branches:{bank_name}:{city}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    async with pool.acquire() as conn:
        if city:
            rows = await conn.fetch(
                "SELECT * FROM branch_info WHERE bank_name = $1 AND city = $2 ORDER BY branch_name",
                bank_name, city,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM branch_info WHERE bank_name = $1 ORDER BY branch_name",
                bank_name,
            )

    data = [dict(r) for r in rows]
    for d in data:
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_atms(
    pool: asyncpg.Pool,
    redis: aioredis.Redis,
    bank_name: str,
    city: str | None = None,
) -> list[dict]:
    cache_key = f"banks:atms:{bank_name}:{city}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    async with pool.acquire() as conn:
        if city:
            rows = await conn.fetch(
                "SELECT * FROM atm_info WHERE bank_name = $1 AND city = $2 ORDER BY branch_name",
                bank_name, city,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM atm_info WHERE bank_name = $1 ORDER BY branch_name",
                bank_name,
            )

    data = [dict(r) for r in rows]
    for d in data:
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_history(
    pool: asyncpg.Pool,
    redis: aioredis.Redis,
    bank_name: str,
) -> dict | None:
    cache_key = f"banks:history:{bank_name}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM historical_events WHERE bank_name = $1",
            bank_name,
        )

    if not row:
        return None

    data = dict(row)
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def search_banks(
    pool: asyncpg.Pool,
    redis: aioredis.Redis,
    query: str,
) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bank_info WHERE bank_name ILIKE $1 ORDER BY bank_name LIMIT 50",
            f"%{query}%",
        )

    data = [dict(r) for r in rows]
    for d in data:
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()

    return data


async def get_dashboard_stats(
    pool: asyncpg.Pool,
    redis: aioredis.Redis,
) -> dict:
    """Aggregated statistics for the main dashboard."""
    cache_key = "banks:dashboard_stats"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    async with pool.acquire() as conn:
        branch_total = await conn.fetchval("SELECT COUNT(*) FROM branch_info")
        atm_total = await conn.fetchval("SELECT COUNT(*) FROM atm_info")

        branch_rows = await conn.fetch(
            "SELECT city, COUNT(*) AS count FROM branch_info "
            "WHERE city IS NOT NULL GROUP BY city ORDER BY count DESC LIMIT 15"
        )
        atm_rows = await conn.fetch(
            "SELECT city, COUNT(*) AS count FROM atm_info "
            "WHERE city IS NOT NULL GROUP BY city ORDER BY count DESC LIMIT 15"
        )

    data = {
        "total_branches": branch_total,
        "total_atms": atm_total,
        "branch_by_city": [{"city": r["city"], "count": r["count"]} for r in branch_rows],
        "atm_by_city": [{"city": r["city"], "count": r["count"]} for r in atm_rows],
    }

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data
