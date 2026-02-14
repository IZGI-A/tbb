"""Financial data service - queries ClickHouse."""

import json
import logging
from decimal import Decimal

import redis.asyncio as aioredis
from clickhouse_driver import Client

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


def _row_to_dict(row: tuple, columns: list[str]) -> dict:
    return {col: (float(v) if isinstance(v, Decimal) else v) for col, v in zip(columns, row)}


async def get_statements(
    ch: Client,
    redis: aioredis.Redis,
    year: int | None = None,
    month: int | None = None,
    bank_name: str | None = None,
    accounting_system: str | None = None,
    main_statement: str | None = None,
    child_statement: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    cache_key = f"fin:stmts:{year}:{month}:{bank_name}:{accounting_system}:{main_statement}:{child_statement}:{limit}:{offset}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    conditions = []
    params = {}
    if year:
        conditions.append("year_id = %(year)s")
        params["year"] = year
    if month:
        conditions.append("month_id = %(month)s")
        params["month"] = month
    if bank_name:
        conditions.append("bank_name = %(bank_name)s")
        params["bank_name"] = bank_name
    if accounting_system:
        conditions.append("accounting_system = %(accounting_system)s")
        params["accounting_system"] = accounting_system
    if main_statement:
        conditions.append("main_statement = %(main_statement)s")
        params["main_statement"] = main_statement
    if child_statement:
        conditions.append("child_statement = %(child_statement)s")
        params["child_statement"] = child_statement

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_query = f"SELECT count() FROM tbb.financial_statements FINAL {where}"
    total = ch.execute(count_query, params)[0][0]

    query = f"""
        SELECT accounting_system, main_statement, child_statement,
               bank_name, year_id, month_id,
               amount_tc, amount_fc, amount_total
        FROM tbb.financial_statements FINAL
        {where}
        ORDER BY year_id DESC, month_id DESC
        LIMIT {int(limit)} OFFSET {int(offset)}
    """

    columns = [
        "accounting_system", "main_statement", "child_statement",
        "bank_name", "year_id", "month_id",
        "amount_tc", "amount_fc", "amount_total",
    ]
    rows = ch.execute(query, params)
    data = [_row_to_dict(r, columns) for r in rows]

    result = {"data": data, "total": total, "limit": limit, "offset": offset}
    await redis.setex(cache_key, CACHE_TTL, json.dumps(result, default=str))
    return result


async def get_summary(
    ch: Client,
    redis: aioredis.Redis,
    year: int | None = None,
    metric: str | None = None,
) -> list[dict]:
    cache_key = f"fin:summary:{year}:{metric}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    conditions = []
    params = {}
    if year:
        conditions.append("year_id = %(year)s")
        params["year"] = year

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT main_statement,
               sum(amount_total) as total,
               count() as cnt
        FROM tbb.financial_statements FINAL
        {where}
        GROUP BY main_statement
        ORDER BY total DESC
    """

    rows = ch.execute(query, params)
    data = [
        {"metric": r[0], "total": float(r[1]) if r[1] else None, "count": r[2]}
        for r in rows
    ]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
    return data


async def get_periods(ch: Client, redis: aioredis.Redis) -> list[dict]:
    cache_key = "fin:periods"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT DISTINCT year_id, month_id
        FROM tbb.financial_statements FINAL
        ORDER BY year_id DESC, month_id DESC
    """
    rows = ch.execute(query)
    data = [{"year_id": r[0], "month_id": r[1]} for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_bank_names(ch: Client, redis: aioredis.Redis) -> list[str]:
    cache_key = "fin:bank_names"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = "SELECT DISTINCT bank_name FROM tbb.financial_statements FINAL ORDER BY bank_name"
    rows = ch.execute(query)
    data = [r[0] for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_main_statements(ch: Client, redis: aioredis.Redis) -> list[str]:
    cache_key = "fin:main_statements"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = "SELECT DISTINCT main_statement FROM tbb.financial_statements FINAL ORDER BY main_statement"
    rows = ch.execute(query)
    data = [r[0] for r in rows if r[0]]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_child_statements(
    ch: Client,
    redis: aioredis.Redis,
    main_statement: str | None = None,
) -> list[str]:
    cache_key = f"fin:child_statements:{main_statement}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    if main_statement:
        query = "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL WHERE main_statement = %(ms)s ORDER BY child_statement"
        rows = ch.execute(query, {"ms": main_statement})
    else:
        query = "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL ORDER BY child_statement"
        rows = ch.execute(query)

    data = [r[0] for r in rows if r[0]]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


async def get_time_series(
    ch: Client,
    redis: aioredis.Redis,
    bank_name: str,
    statement: str | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
) -> list[dict]:
    cache_key = f"fin:ts:{bank_name}:{statement}:{from_year}:{to_year}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    conditions = ["bank_name = %(bank_name)s"]
    params = {"bank_name": bank_name}
    if statement:
        conditions.append("main_statement = %(statement)s")
        params["statement"] = statement
    if from_year:
        conditions.append("year_id >= %(from_year)s")
        params["from_year"] = from_year
    if to_year:
        conditions.append("year_id <= %(to_year)s")
        params["to_year"] = to_year

    where = f"WHERE {' AND '.join(conditions)}"

    query = f"""
        SELECT year_id, month_id, sum(amount_total) as amount_total
        FROM tbb.financial_statements FINAL
        {where}
        GROUP BY year_id, month_id
        ORDER BY year_id, month_id
    """

    rows = ch.execute(query, params)
    data = [
        {"year_id": r[0], "month_id": r[1], "amount_total": float(r[2]) if r[2] else None}
        for r in rows
    ]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
    return data
