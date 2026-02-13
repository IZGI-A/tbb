"""Regional statistics service - queries ClickHouse."""

import json
import logging
from decimal import Decimal

import redis.asyncio as aioredis
from clickhouse_driver import Client

logger = logging.getLogger(__name__)

CACHE_TTL = 21600  # 6 hours


async def get_stats(
    ch: Client,
    redis: aioredis.Redis,
    region: str | None = None,
    metric: str | None = None,
    year: int | None = None,
) -> list[dict]:
    cache_key = f"reg:stats:{region}:{metric}:{year}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    conditions = []
    params = {}
    if region:
        conditions.append("region = %(region)s")
        params["region"] = region
    if metric:
        conditions.append("metric = %(metric)s")
        params["metric"] = metric
    if year:
        conditions.append("year_id = %(year)s")
        params["year"] = year

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT region, metric, year_id, value
        FROM tbb.region_statistics FINAL
        {where}
        ORDER BY year_id DESC, region
        LIMIT 1000
    """

    rows = ch.execute(query, params)
    data = [
        {
            "region": r[0],
            "metric": r[1],
            "year_id": r[2],
            "value": float(r[3]) if r[3] else None,
        }
        for r in rows
    ]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
    return data


async def get_regions(ch: Client, redis: aioredis.Redis) -> list[str]:
    cache_key = "reg:list"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = "SELECT DISTINCT region FROM tbb.region_statistics FINAL ORDER BY region"
    rows = ch.execute(query)
    data = [r[0] for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_metrics(ch: Client, redis: aioredis.Redis) -> list[str]:
    cache_key = "reg:metrics"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = "SELECT DISTINCT metric FROM tbb.region_statistics FINAL ORDER BY metric"
    rows = ch.execute(query)
    data = [r[0] for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_comparison(
    ch: Client,
    redis: aioredis.Redis,
    metric: str,
    year: int,
) -> list[dict]:
    cache_key = f"reg:cmp:{metric}:{year}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT region, value
        FROM tbb.region_statistics FINAL
        WHERE metric = %(metric)s AND year_id = %(year)s
        ORDER BY value DESC
    """
    rows = ch.execute(query, {"metric": metric, "year": year})
    data = [{"region": r[0], "value": float(r[1]) if r[1] else None} for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
    return data
