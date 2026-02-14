"""Risk center service - queries ClickHouse."""

import json
import logging

import redis.asyncio as aioredis
from clickhouse_driver import Client

logger = logging.getLogger(__name__)

CACHE_TTL = 21600  # 6 hours


async def get_data(
    ch: Client,
    redis: aioredis.Redis,
    report_name: str | None = None,
    category: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> list[dict]:
    cache_key = f"risk:data:{report_name}:{category}:{year}:{month}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    conditions = []
    params = {}
    if report_name:
        conditions.append("report_name = %(report_name)s")
        params["report_name"] = report_name
    if category:
        conditions.append("category = %(category)s")
        params["category"] = category
    if year:
        conditions.append("year_id = %(year)s")
        params["year"] = year
    if month:
        conditions.append("month_id = %(month)s")
        params["month"] = month

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT report_name, category, person_count, quantity, amount,
               year_id, month_id
        FROM tbb.risk_center FINAL
        {where}
        ORDER BY year_id DESC, month_id DESC
        LIMIT 1000
    """

    rows = ch.execute(query, params)
    data = [
        {
            "report_name": r[0],
            "category": r[1],
            "person_count": r[2],
            "quantity": r[3],
            "amount": float(r[4]) if r[4] else None,
            "year_id": r[5],
            "month_id": r[6],
        }
        for r in rows
    ]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
    return data


async def get_reports(ch: Client, redis: aioredis.Redis) -> list[str]:
    cache_key = "risk:reports"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = "SELECT DISTINCT report_name FROM tbb.risk_center FINAL ORDER BY report_name"
    rows = ch.execute(query)
    data = [r[0] for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_periods(ch: Client, redis: aioredis.Redis) -> list[dict]:
    cache_key = "risk:periods"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT DISTINCT year_id, month_id
        FROM tbb.risk_center FINAL
        ORDER BY year_id DESC, month_id DESC
    """
    rows = ch.execute(query)
    data = [{"year_id": r[0], "month_id": r[1]} for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_categories(
    ch: Client,
    redis: aioredis.Redis,
    report_name: str,
) -> list[str]:
    cache_key = f"risk:cats:{report_name}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT DISTINCT category
        FROM tbb.risk_center FINAL
        WHERE report_name = %(report_name)s
        ORDER BY category
    """
    rows = ch.execute(query, {"report_name": report_name})
    data = [r[0] for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data
