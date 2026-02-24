"""Bank Risk Analysis service — Z-Score calculation.

Based on Çolak, Deniz, Korkmaz & Yılmaz (2024), Section IV.III "Bank Risk":
  Z-Score = (Capital Ratio + ROA) / σ(ROA)

Where:
  - Capital Ratio = Equity / Total Assets
  - ROA = Net Income / Total Assets
  - σ(ROA) = standard deviation of ROA over a 12-month rolling window

Higher Z-Score → greater distance to default → lower risk.
"""

import json
import logging
import math
from decimal import Decimal

import redis.asyncio as aioredis
from clickhouse_driver import Client

from db.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_TTL = 3600

# Same excluded banks as liquidity analysis
_STATE_BANKS = {
    "T.C. Ziraat Bankası A.Ş.",
    "Türkiye Cumhuriyeti Ziraat Bankası A.Ş.",
    "Türkiye Halk Bankası A.Ş.",
    "Türkiye Vakıflar Bankası T.A.O.",
    "Ziraat Dinamik Banka A.Ş. (dijital banka)",
}

_PRIVATE_BANKS = {
    "Akbank T.A.Ş.",
    "Anadolubank A.Ş.",
    "Fibabanka A.Ş.",
    "Şekerbank T.A.Ş.",
    "Turkish Bank A.Ş.",
    "Türkiye İş Bankası A.Ş.",
    "Yapı ve Kredi Bankası A.Ş.",
}


def _get_bank_group(name: str) -> str:
    if name in _STATE_BANKS:
        return "Kamu"
    if name in _PRIVATE_BANKS:
        return "Ozel"
    return "Yabanci"


_EXCLUDED_BANKS = (
    "Türkiye Bankacılık Sistemi",
    " Mevduat Bankaları",
    "Mevduat Bankaları",
    "Kamusal Sermayeli Mevduat Bankaları",
    "Özel Sermayeli Mevduat Bankaları",
    "Yabancı Sermayeli Bankalar",
    "Kalkınma ve Yatırım Bankaları",
    "Tasarruf Mevduatı Sigorta Fonuna Devredilen Bankalar",
    "Türk Eximbank",
    "Türkiye Kalkınma ve Yatırım Bankası A.Ş.",
    "İller Bankası A.Ş.",
    "Aktif Yatırım Bankası A.Ş.",
    "Aytemiz Yatırım Bankası A.Ş.",
    "BankPozitif Kredi ve Kalkınma Bankası A.Ş.",
    "D Yatırım Bankası A.Ş.",
    "Destek Yatırım Bankası A.Ş.",
    "Diler Yatırım Bankası A.Ş.",
    "GSD Yatırım Bankası A.Ş.",
    "Golden Global Yatırım Bankası A.Ş.",
    "Hedef Yatırım Bankası A.Ş.",
    "Misyon Yatırım Bankası A.Ş.",
    "Nurol Yatırım Bankası A.Ş.",
    "Q Yatırım Bankası A.Ş.",
    "Tera Yatırım Bankası A.Ş.",
    "Türkiye Sınai Kalkınma Bankası A.Ş.",
    "İstanbul Takas ve Saklama Bankası A.Ş.",
    "Bank of America Yatırım Bank A.Ş.",
    "Pasha Yatırım Bankası A.Ş.",
    "Standard Chartered Yatırım Bankası Türk A.Ş.",
)


def _exclude_clause() -> str:
    escaped = ", ".join(f"'{b}'" for b in _EXCLUDED_BANKS)
    return f"bank_name NOT IN ({escaped})"


def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _fetch_bank_financials(ch: Client, accounting_system: str | None = None) -> list[dict]:
    """Fetch equity, net income, total assets per bank per period."""
    pct = "%%"
    acct = ""
    if accounting_system:
        acct = f"AND accounting_system LIKE '{pct}{accounting_system}{pct}'"
    else:
        acct = f"AND accounting_system LIKE '{pct}SOLO{pct}'"

    query = f"""
        SELECT
            bank_name,
            year_id,
            month_id,
            sumIf(amount_total,
                startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
                AND child_statement = 'XVI. ÖZKAYNAKLAR') AS equity,
            sumIf(amount_total,
                startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS total_assets,
            sumIf(amount_total,
                (startsWith(main_statement, '4. GELİR-GİDER TABLOSU')
                 OR startsWith(main_statement, '5. KAR VEYA ZARAR'))
                AND child_statement = 'XXV. DÖNEM NET KARI/ZARARI (XIX+XXIV)') AS net_income
        FROM tbb.financial_statements
        WHERE {_exclude_clause()}
            {acct}
        GROUP BY bank_name, year_id, month_id
        HAVING total_assets > 0
        ORDER BY bank_name, year_id, month_id
    """
    rows = ch.execute(query)
    return [
        {
            "bank_name": r[0],
            "year_id": r[1],
            "month_id": r[2],
            "equity": _to_float(r[3]),
            "total_assets": _to_float(r[4]),
            "net_income": _to_float(r[5]),
        }
        for r in rows
    ]


def _compute_zscore(rows: list[dict], window: int = 12) -> list[dict]:
    """Compute Z-Score per bank-period using a rolling ROA std dev window."""
    # Group by bank
    by_bank: dict[str, list[dict]] = {}
    for r in rows:
        by_bank.setdefault(r["bank_name"], []).append(r)

    results = []
    for bank_name, bank_rows in by_bank.items():
        # Sort chronologically
        bank_rows.sort(key=lambda x: (x["year_id"], x["month_id"]))

        # Compute ROA and capital ratio for each period
        for r in bank_rows:
            ta = r["total_assets"]
            r["roa"] = r["net_income"] / ta if ta else 0.0
            r["capital_ratio"] = r["equity"] / ta if ta else 0.0

        # Rolling std dev of ROA
        for i, r in enumerate(bank_rows):
            start = max(0, i - window + 1)
            roa_window = [bank_rows[j]["roa"] for j in range(start, i + 1)]

            if len(roa_window) < 2:
                # Not enough periods for std dev — use absolute ROA as proxy
                # so first-period banks still appear with an approximate Z-Score
                abs_roa = abs(r["roa"]) if r["roa"] != 0 else 1e-6
                r["roa_std"] = abs_roa
                r["z_score"] = (r["capital_ratio"] + r["roa"]) / abs_roa
                continue

            mean_roa = sum(roa_window) / len(roa_window)
            variance = sum((x - mean_roa) ** 2 for x in roa_window) / (len(roa_window) - 1)
            std_roa = math.sqrt(variance) if variance > 0 else 0.0

            r["roa_std"] = std_roa
            if std_roa > 0:
                r["z_score"] = (r["capital_ratio"] + r["roa"]) / std_roa
            else:
                # All ROAs identical in window — use absolute ROA as fallback
                abs_roa = abs(r["roa"]) if r["roa"] != 0 else 1e-6
                r["roa_std"] = abs_roa
                r["z_score"] = (r["capital_ratio"] + r["roa"]) / abs_roa

        results.extend(bank_rows)

    return results


async def get_zscore_ranking(
    ch: Client,
    redis: aioredis.Redis,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> list[dict]:
    """Get Z-Score ranking for all banks in a given period."""
    cache_key = f"risk:zscore:{year}:{month}:{accounting_system or 'default'}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return json.loads(cached)

    rows = _fetch_bank_financials(ch, accounting_system)
    all_scores = _compute_zscore(rows)

    # Filter to requested period
    period_scores = [
        {
            "bank_name": r["bank_name"],
            "z_score": round(r["z_score"], 4) if r["z_score"] is not None else None,
            "roa": round(r["roa"] * 100, 4),
            "capital_ratio": round(r["capital_ratio"] * 100, 4),
            "roa_std": round(r["roa_std"] * 100, 6) if r["roa_std"] is not None else None,
            "total_assets": r["total_assets"],
            "equity": r["equity"],
            "net_income": r["net_income"],
        }
        for r in all_scores
        if r["year_id"] == year and r["month_id"] == month and r["z_score"] is not None
    ]
    period_scores.sort(key=lambda x: x["z_score"] or 0, reverse=True)

    await cache_set(redis, cache_key, json.dumps(period_scores), ttl=CACHE_TTL)
    return period_scores


async def get_zscore_time_series(
    ch: Client,
    redis: aioredis.Redis,
    bank_name: str | None = None,
    accounting_system: str | None = None,
) -> list[dict]:
    """Get Z-Score time series, optionally for a specific bank."""
    cache_key = f"risk:zscore-ts:{bank_name or 'all'}:{accounting_system or 'default'}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return json.loads(cached)

    rows = _fetch_bank_financials(ch, accounting_system)
    all_scores = _compute_zscore(rows)

    result = [
        {
            "bank_name": r["bank_name"],
            "year_id": r["year_id"],
            "month_id": r["month_id"],
            "z_score": round(r["z_score"], 4) if r["z_score"] is not None else None,
            "roa": round(r["roa"] * 100, 4),
            "capital_ratio": round(r["capital_ratio"] * 100, 4),
        }
        for r in all_scores
        if r["z_score"] is not None and (bank_name is None or r["bank_name"] == bank_name)
    ]

    await cache_set(redis, cache_key, json.dumps(result), ttl=CACHE_TTL)
    return result


async def get_lc_risk_relationship(
    ch: Client,
    redis: aioredis.Redis,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> list[dict]:
    """Get LC and Z-Score together for scatter plot analysis."""
    from api.services.liquidity_service import (
        get_liquidity_creation,
    )

    cache_key = f"risk:lc-risk:{year}:{month}:{accounting_system or 'default'}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return json.loads(cached)

    # Get Z-Scores
    zscore_data = await get_zscore_ranking(ch, redis, year, month, accounting_system)
    zscore_map = {r["bank_name"]: r for r in zscore_data}

    # Get LC data
    lc_data = await get_liquidity_creation(ch, redis, year, month, accounting_system)
    lc_map = {r["bank_name"]: r for r in lc_data}

    # Merge
    result = []
    for bank_name in set(zscore_map.keys()) & set(lc_map.keys()):
        z = zscore_map[bank_name]
        lc = lc_map[bank_name]
        result.append({
            "bank_name": bank_name,
            "z_score": z["z_score"],
            "lc_nonfat": lc["lc_nonfat"],
            "roa": z["roa"],
            "capital_ratio": z["capital_ratio"],
            "total_assets": z["total_assets"],
            "bank_group": _get_bank_group(bank_name),
        })

    result.sort(key=lambda x: x["z_score"] or 0, reverse=True)

    await cache_set(redis, cache_key, json.dumps(result), ttl=CACHE_TTL)
    return result
