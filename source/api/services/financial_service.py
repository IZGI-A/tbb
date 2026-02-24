"""Financial data service - queries ClickHouse."""

import logging
from decimal import Decimal

import redis.asyncio as aioredis
from clickhouse_driver import Client

from db.cache import cache_get, cache_set

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
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

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
        conditions.append("accounting_system LIKE %(accounting_system)s")
        params["accounting_system"] = f"%{accounting_system}%"
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
    await cache_set(redis, cache_key, result, CACHE_TTL, default=str)
    return result


async def get_summary(
    ch: Client,
    redis: aioredis.Redis,
    year: int | None = None,
    metric: str | None = None,
    accounting_system: str | None = None,
) -> list[dict]:
    cache_key = f"fin:summary:{year}:{metric}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    conditions = []
    params = {}
    if year:
        conditions.append("year_id = %(year)s")
        params["year"] = year
    if accounting_system:
        conditions.append("accounting_system LIKE %(accounting_system)s")
        params["accounting_system"] = f"%{accounting_system}%"

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

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data


async def get_periods(ch: Client, redis: aioredis.Redis) -> list[dict]:
    cache_key = "fin:periods"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    query = """
        SELECT DISTINCT year_id, month_id
        FROM tbb.financial_statements FINAL
        ORDER BY year_id DESC, month_id DESC
    """
    rows = ch.execute(query)
    data = [{"year_id": r[0], "month_id": r[1]} for r in rows]

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_bank_names(ch: Client, redis: aioredis.Redis, accounting_system: str | None = None) -> list[str]:
    cache_key = f"fin:bank_names:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    query = "SELECT DISTINCT bank_name FROM tbb.financial_statements FINAL"
    params = {}
    if accounting_system:
        query += " WHERE accounting_system LIKE %(accounting_system)s"
        params["accounting_system"] = f"%{accounting_system.upper()}%"
    query += " ORDER BY bank_name"
    rows = ch.execute(query, params)
    data = [r[0] for r in rows]

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_main_statements(ch: Client, redis: aioredis.Redis) -> list[str]:
    cache_key = "fin:main_statements"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    query = "SELECT DISTINCT main_statement FROM tbb.financial_statements FINAL ORDER BY main_statement"
    rows = ch.execute(query)
    data = [r[0] for r in rows if r[0]]

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_child_statements(
    ch: Client,
    redis: aioredis.Redis,
    main_statement: str | None = None,
) -> list[str]:
    cache_key = f"fin:child_statements:{main_statement}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    if main_statement:
        query = "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL WHERE main_statement = %(ms)s ORDER BY child_statement"
        rows = ch.execute(query, {"ms": main_statement})
    else:
        query = "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL ORDER BY child_statement"
        rows = ch.execute(query)

    data = [r[0] for r in rows if r[0]]

    await cache_set(redis, cache_key, data, CACHE_TTL)
    return data


async def get_time_series(
    ch: Client,
    redis: aioredis.Redis,
    bank_name: str,
    statement: str | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
    accounting_system: str | None = None,
) -> list[dict]:
    cache_key = f"fin:ts:{bank_name}:{statement}:{from_year}:{to_year}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

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
    if accounting_system:
        conditions.append("accounting_system LIKE %(accounting_system)s")
        params["accounting_system"] = f"%{accounting_system}%"

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

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data


# --- Financial Ratio Definitions ---
_RATIO_DEFS = {
    "ROA": {"label": "ROA (Aktif Karlılığı) %", "desc": "Net Kar / Toplam Aktif"},
    "ROE": {"label": "ROE (Özkaynak Karlılığı) %", "desc": "Net Kar / Özkaynaklar"},
    "NIM": {"label": "NIM (Net Faiz Marjı) %", "desc": "Net Faiz Geliri / Toplam Aktif"},
    "PROVISION": {"label": "Karşılık Oranı %", "desc": "Beklenen Zarar Karşılıkları / Toplam Kredi"},
    "LEVERAGE": {"label": "Kaldıraç (Özkaynak/Aktif) %", "desc": "Özkaynaklar / Toplam Aktif"},
    "FX_SHARE": {"label": "YP Aktif Payı %", "desc": "YP Aktifler / Toplam Aktif"},
}


async def get_ratio_types() -> list[dict]:
    """Return available ratio type definitions."""
    return [{"key": k, **v} for k, v in _RATIO_DEFS.items()]


async def get_financial_ratios(
    ch: Client,
    redis: aioredis.Redis,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> list[dict]:
    """Compute key financial ratios per bank for a given period."""
    cache_key = f"fin:ratios:{year}:{month}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    query = """
        SELECT
            bank_name,
            sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS total_assets,
            sumIf(amount_total, startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
                AND child_statement = 'XVI. ÖZKAYNAKLAR') AS equity,
            sumIf(amount_total, startsWith(main_statement, '4. GELİR-GİDER TABLOSU')
                AND child_statement = 'XXV. DÖNEM NET KARI/ZARARI (XIX+XXIV)') AS net_profit,
            sumIf(amount_total, startsWith(main_statement, '4. GELİR-GİDER TABLOSU')
                AND child_statement = 'III. NET FAİZ GELİRİ/GİDERİ (I - II)') AS net_interest_income,
            sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = '2.1. Krediler') AS total_loans,
            sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = '2.5 Beklenen Zarar Karşılıkları (-) (TFRS 9 uygulayan b.)') AS credit_provisions,
            sumIf(amount_fc, startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS assets_fc,
            sumIf(amount_fc, startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
                AND child_statement = 'XVII. YÜKÜMLÜLÜKLER TOPLAMI') AS liabilities_fc
        FROM tbb.financial_statements FINAL
        WHERE year_id = %(year)s AND month_id = %(month)s
          AND accounting_system LIKE %(acct_sys)s
          AND bank_name NOT IN (
              'Türkiye Bankacılık Sistemi',
              ' Mevduat Bankaları',
              'Mevduat Bankaları',
              'Kamusal Sermayeli Mevduat Bankaları',
              'Özel Sermayeli Mevduat Bankaları',
              'Yabancı Sermayeli Bankalar',
              'Kalkınma ve Yatırım Bankaları',
              'Tasarruf Mevduatı Sigorta Fonuna Devredilen Bankalar'
          )
        GROUP BY bank_name
        HAVING total_assets > 0
        ORDER BY total_assets DESC
    """
    acct_sys_pattern = f"%{accounting_system}%" if accounting_system else "%"
    rows = ch.execute(query, {"year": year, "month": month, "acct_sys": acct_sys_pattern})

    data = []
    for r in rows:
        bank = r[0]
        total_assets = float(r[1]) if r[1] else 0
        equity = float(r[2]) if r[2] else 0
        net_profit = float(r[3]) if r[3] else 0
        nim_val = float(r[4]) if r[4] else 0
        total_loans = float(r[5]) if r[5] else 0
        provisions = float(r[6]) if r[6] else 0
        assets_fc = float(r[7]) if r[7] else 0
        liabilities_fc = float(r[8]) if r[8] else 0

        if total_assets <= 0:
            continue

        roa = round(net_profit / total_assets * 100, 2)
        roe = round(net_profit / equity * 100, 2) if equity else None
        nim = round(nim_val / total_assets * 100, 2)
        prov_rate = round(abs(provisions) / total_loans * 100, 2) if total_loans else None
        leverage = round(equity / total_assets * 100, 2)
        fx_share = round(assets_fc / total_assets * 100, 2)

        data.append({
            "bank_name": bank,
            "total_assets": total_assets,
            "ROA": roa,
            "ROE": roe,
            "NIM": nim,
            "PROVISION": prov_rate,
            "LEVERAGE": leverage,
            "FX_SHARE": fx_share,
        })

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data
