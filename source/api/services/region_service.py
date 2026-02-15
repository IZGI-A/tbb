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


async def get_periods(ch: Client, redis: aioredis.Redis) -> list[dict]:
    cache_key = "reg:periods"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT DISTINCT year_id
        FROM tbb.region_statistics FINAL
        ORDER BY year_id DESC
    """
    rows = ch.execute(query)
    data = [{"year_id": r[0]} for r in rows]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


_CREDIT_SECTORS = [
    "İht.Kred./ Denizcilik",
    "İht.Kred./ Diğer",
    "İht.Kred./ Gayrimenkul",
    "İht.Kred./ Mesleki",
    "İht.Kred./ Tarım",
    "İht.Kred./ Turizm",
]

_SECTOR_SHORT = {s: s.replace("İht.Kred./ ", "") for s in _CREDIT_SECTORS}


async def get_credit_hhi(
    ch: Client,
    redis: aioredis.Redis,
    year: int,
) -> list[dict]:
    """Compute HHI and sectoral share breakdown per region."""
    cache_key = f"reg:hhi:{year}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT region, metric, value
        FROM tbb.region_statistics FINAL
        WHERE year_id = %(year)s
          AND metric IN (
              'İht.Kred./ Denizcilik', 'İht.Kred./ Diğer',
              'İht.Kred./ Gayrimenkul', 'İht.Kred./ Mesleki',
              'İht.Kred./ Tarım', 'İht.Kred./ Turizm'
          )
          AND region NOT IN ('Tüm Bölgeler', 'Yabancı Ülkeler', 'İller Bankası', 'Kıbrıs')
        ORDER BY region
    """
    rows = ch.execute(query, {"year": year})

    region_sectors: dict[str, dict[str, float]] = {}
    for r in rows:
        region, metric, value = r[0], r[1], float(r[2]) if r[2] else 0.0
        if region not in region_sectors:
            region_sectors[region] = {}
        region_sectors[region][metric] = value

    data = []
    for region, sectors in region_sectors.items():
        total = sum(sectors.values())
        if total <= 0:
            continue
        hhi = sum((v / total * 100) ** 2 for v in sectors.values())
        dominant = max(sectors, key=sectors.get)  # type: ignore[arg-type]

        # Build sector shares dict with short names
        shares = {}
        for full_name, short_name in _SECTOR_SHORT.items():
            val = sectors.get(full_name, 0)
            shares[short_name] = round(val / total * 100, 1) if total else 0

        data.append({
            "region": region,
            "hhi": round(hhi, 0),
            "dominant_sector": _SECTOR_SHORT[dominant],
            "shares": shares,
        })

    data.sort(key=lambda x: x["hhi"], reverse=True)

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
    return data


async def get_loan_deposit_ratio(
    ch: Client,
    redis: aioredis.Redis,
    year: int,
) -> list[dict]:
    """Compute Loan-to-Deposit ratio per region for a given year."""
    cache_key = f"reg:ldr:{year}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = """
        SELECT
            region,
            sumIf(value, metric IN (
                'İht.Dışı Krediler',
                'İht.Kred./ Denizcilik', 'İht.Kred./ Diğer',
                'İht.Kred./ Gayrimenkul', 'İht.Kred./ Mesleki',
                'İht.Kred./ Tarım', 'İht.Kred./ Turizm'
            )) AS total_credit,
            sumIf(value, metric IN (
                'Tasarruf Mevduatı', 'Bankalar Mevduatı',
                'Ticari Kuruluşlar Mevduatı', 'Döviz Tevdiat Hesapları',
                'Resmi Kuruluşlar Mevduatı', 'Diğer Mevduat',
                'Altın Depo Hesabı'
            )) AS total_deposit
        FROM tbb.region_statistics FINAL
        WHERE year_id = %(year)s
          AND region NOT IN ('Tüm Bölgeler', 'Yabancı Ülkeler', 'İller Bankası', 'Kıbrıs')
        GROUP BY region
        HAVING total_deposit > 0
        ORDER BY total_credit / total_deposit DESC
    """
    rows = ch.execute(query, {"year": year})
    data = [
        {
            "region": r[0],
            "total_credit": float(r[1]) if r[1] else 0,
            "total_deposit": float(r[2]) if r[2] else 0,
            "ratio": round(float(r[1]) / float(r[2]), 4) if r[2] else None,
        }
        for r in rows
    ]

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data, default=str))
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
