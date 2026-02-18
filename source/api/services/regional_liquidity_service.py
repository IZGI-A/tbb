"""Regional Liquidity Creation analysis service.

Distributes per-bank LC across cities weighted by branch presence.
Each bank's LC amount (lc_nonfat * total_assets) is allocated to cities
proportional to the bank's branch count in that city.
"""

import json
import logging
from collections import defaultdict

import asyncpg
import redis.asyncio as aioredis
from clickhouse_driver import Client

from db.cache import cache_get, cache_set
from api.services.liquidity_service import get_liquidity_creation

logger = logging.getLogger(__name__)

CACHE_TTL = 3600


async def get_regional_liquidity(
    ch: Client,
    redis: aioredis.Redis,
    pg: asyncpg.Pool,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> list[dict]:
    """Compute city-level LC distribution weighted by branch presence."""
    cache_key = f"regional_liq:{year}:{month}:{accounting_system or 'default'}"
    cached = await cache_get(redis, cache_key)
    if cached:
        if isinstance(cached, str):
            return json.loads(cached)
        return cached

    # 1. Per-bank LC from existing service
    bank_lc_data = await get_liquidity_creation(ch, redis, year, month, accounting_system)

    bank_lc_map: dict[str, dict] = {}
    for bd in bank_lc_data:
        lc_amount = bd["lc_nonfat"] * bd["total_assets"]
        bank_lc_map[bd["bank_name"]] = {
            "lc_amount": lc_amount,
            "total_assets": bd["total_assets"],
        }

    # 2. Branch distribution from PostgreSQL
    async with pg.acquire() as conn:
        branch_rows = await conn.fetch(
            "SELECT bank_name, city, COUNT(*) AS cnt "
            "FROM branch_info "
            "WHERE city IS NOT NULL AND city != '' "
            "GROUP BY bank_name, city"
        )

    # Build per-bank city distribution
    bank_city_branches: dict[str, dict[str, int]] = defaultdict(dict)
    bank_total_branches: dict[str, int] = defaultdict(int)
    for r in branch_rows:
        bname, city, cnt = r["bank_name"], r["city"], r["cnt"]
        bank_city_branches[bname][city] = cnt
        bank_total_branches[bname] += cnt

    # 3. Distribute LC to cities (only LC-eligible banks)
    city_lc: dict[str, float] = defaultdict(float)
    city_ta: dict[str, float] = defaultdict(float)
    city_branch_totals: dict[str, int] = defaultdict(int)
    city_bank_sets: dict[str, set] = defaultdict(set)

    for bank_name, lc_info in bank_lc_map.items():
        if bank_name not in bank_city_branches:
            continue
        total_br = bank_total_branches[bank_name]
        if total_br == 0:
            continue
        for city, city_br in bank_city_branches[bank_name].items():
            weight = city_br / total_br
            city_lc[city] += lc_info["lc_amount"] * weight
            city_ta[city] += lc_info["total_assets"] * weight
            city_branch_totals[city] += city_br
            city_bank_sets[city].add(bank_name)

    # 4. Build result
    result = []
    for city in city_lc.keys():
        lc = city_lc.get(city, 0.0)
        ta = city_ta.get(city, 0.0)
        avg_ratio = round(lc / ta, 6) if ta > 0 else None
        result.append({
            "city": city,
            "lc_amount": round(lc, 2),
            "branch_count": city_branch_totals.get(city, 0),
            "bank_count": len(city_bank_sets.get(city, set())),
            "avg_lc_ratio": avg_ratio,
        })

    result.sort(key=lambda x: x["lc_amount"], reverse=True)

    await cache_set(redis, cache_key, json.dumps(result), ttl=CACHE_TTL)
    return result
