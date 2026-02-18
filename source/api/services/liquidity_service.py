"""Liquidity Creation analysis service.

Based on:
  Çolak, Deniz, Korkmaz & Yılmaz (2024),
  "A Panorama of Liquidity Creation in Turkish Banking Industry",
  TCMB Working Paper No: 24/09 — Table 2 classification.

Implements both measures:
  - cat nonfat: on-balance sheet items only (baseline)
  - cat fat:    includes off-balance sheet (OBS) activities
"""

import logging
from decimal import Decimal

import asyncpg
import redis.asyncio as aioredis
from clickhouse_driver import Client

from db.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Balance sheet item classification — Çolak et al. (2024), Table 2
# ---------------------------------------------------------------------------
# Adapted from: "A Panorama of Liquidity Creation in Turkish Banking Industry"
# TCMB Working Paper 24/09, which adapts B&B (2009) for Turkish banking.
#
# IMPORTANT: Use ONE consistent hierarchy level per section to avoid
# double counting. For section I (Financial Assets) and II (Amortized Cost FA),
# use numbered sub-items (1.1, 1.2, 2.1, etc.) — NOT the Roman numeral
# subtotals which already include those sub-items.
#
# Notes on TBB data granularity vs the paper's BRSA data:
# - Deposits: paper splits demand+term<=3mo (liquid) vs rest (semi-liquid);
#   TBB has only "I. MEVDUAT" → treated as liquid (conservative).
# - Loans: paper splits mortgage (semi-liquid) vs non-mortgage (illiquid);
#   TBB has only "2.1. Krediler" → treated as illiquid.
# - Cash/CBRT: paper splits cash (liquid) vs CBRT receivables (semi-liquid);
#   TBB has "1.1 Nakit ve Nakit Benzerleri" → treated as liquid.

# Assets: child_statement values under startsWith(main_statement, '1. VARLIKLAR')
_LIQUID_ASSETS = (
    "1.1 Nakit ve Nakit Benzerleri",                                        # cash & equivalents (paper: Cash=liquid, CBRT=semi-liquid; combined)
    "1.2 Gerçeğe Uygun Değer Farkı Kar Zarara Yansıtılan FV",             # securities at FV through P/L
    "1.3 Gerçeğe Uygun Değer Farkı Diğer Kapsamlı Gelire Yansıtılan FV",  # securities available-for-sale (paper: liquid)
)

_SEMI_LIQUID_ASSETS = (
    "1.4 Türev Finansal Varlıklar",                                         # derivative assets
    "2.2 Kiralama İşlemlerinden Alacaklar",                                 # leasing receivables
    "2.3 Faktoring Alacakları",                                             # factoring receivables
    "2.4 İtfa Edilmiş Maliyeti ile Ölçülen Diğer Finansal Varlıklar",      # securities held to maturity
    "III.SATIŞ AMAÇ.ELDE TUTU.VE DURD.FAAL.İLİŞKİN DURAN VARL.(Net)",    # assets to be sold
    "IV. ORTAKLIK YATIRIMLARI",                                             # affiliates, subsidiaries
    "VIII. CARİ VERGİ VARLIĞI",                                            # current tax asset
    "IX. ERTELENMİŞ VERGİ VARLIĞI",                                        # deferred tax asset
)

_ILLIQUID_ASSETS = (
    "2.1. Krediler",                                                        # loans (paper: excl. mortgage=illiquid; combined)
    "V. MADDİ DURAN VARLIKLAR(Net)",                                        # premises & equipment
    "VI. MADDİ OLMAYAN DURAN VARLIKLAR(Net)",                               # intangible assets
    "VII. YATIRIM AMAÇLI GAYRİMENKULLER (NET)",                            # investment property
    "X. DİĞER AKTİFLER (Net)",                                             # other assets
)

# Liabilities: child_statement values under startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
_LIQUID_LIABILITIES = (
    "I. MEVDUAT",                                                           # deposits (paper: demand+term<=3mo; combined)
    "II. ALINAN KREDİLER",                                                  # payables to banks (paper: liquid)
    "III. PARA PİYASALARINA BORÇLAR",                                       # money market + repo (paper: liquid)
    "V. FONLAR",                                                            # funds (paper: liquid)
    "VI. GERÇEĞE UYGUN DEĞER FARKI KAR ZARARA YANSITILAN FİNANSAL YÜKÜMLÜLÜKLER",  # FV liabilities
)

_SEMI_LIQUID_LIABILITIES = (
    "VII. TÜREV FİNANSAL YÜKÜMLÜLÜKLER",                                   # derivative liabilities
    "VIII. FAKTORİNG YÜKÜMLÜLÜKLERİ",                                     # factoring liabilities
    "X. KARŞILIKLAR",                                                       # provisions (paper: semi-liquid)
    "XI. CARİ VERGİ BORCU",                                                # taxes, duties (paper: semi-liquid)
    "XII. ERTELENMİŞ VERGİ BORCU",                                         # deferred tax (paper: semi-liquid)
    "XIII. SATIŞ AMAÇLI ELDE TUTU.VE DURDU. FAAL.İLİŞKİN DURAN VARLIK BORÇLARI (Net)",  # held for sale liab.
    "XV. DİĞER YÜKÜMLÜLÜKLER",                                             # other liabilities (paper: semi-liquid)
)

_ILLIQUID_LIABILITIES_EQUITY = (
    "IV. İHRAÇ EDİLEN MENKUL KIYMETLER (Net)",                             # securities issued
    "IX. KİRALAMA İŞLEMLERİNDEN YÜKÜMLÜLÜKLER (Net)",                      # liabilities from leases
    "XIV. SERMAYE BENZERİ BORÇLANMA ARAÇLARI",                              # subordinated debt
    "XVI. ÖZKAYNAKLAR",                                                     # total shareholders' equity
)

# Off-Balance Sheet: child_statement values under startsWith(main_statement, '3. NAZIM HESAPLAR')
_ILLIQUID_OBS = (
    "I. GARANTİ ve KEFALETLER",                                            # guarantees & sureties
    "2.1.Cayılamaz Taahhütler",                                             # irrevocable commitments
)

_SEMI_LIQUID_OBS = (
    "III. TÜREV FİNANSAL ARAÇLAR",                                         # OBS derivatives
    "2.2.Cayılabilir Taahhütler",                                           # revocable commitments
)

# Bank names to exclude: sector aggregates + development/investment banks
# (Kalkinma ve Yatirim Bankalari are excluded per Çolak et al. 2024 methodology
#  which focuses on commercial/deposit banks only.)
_EXCLUDED_BANKS = (
    # Sector aggregates
    "Türkiye Bankacılık Sistemi",
    " Mevduat Bankaları",
    "Mevduat Bankaları",
    "Kamusal Sermayeli Mevduat Bankaları",
    "Özel Sermayeli Mevduat Bankaları",
    "Yabancı Sermayeli Bankalar",
    "Kalkınma ve Yatırım Bankaları",
    "Tasarruf Mevduatı Sigorta Fonuna Devredilen Bankalar",
    # Kamusal Sermayeli Kalkınma ve Yatırım Bankaları
    "Türk Eximbank",
    "Türkiye Kalkınma ve Yatırım Bankası A.Ş.",
    "İller Bankası A.Ş.",
    # Özel Sermayeli Kalkınma ve Yatırım Bankaları
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
    # Yabancı Sermayeli Kalkınma ve Yatırım Bankaları
    "Bank of America Yatırım Bank A.Ş.",
    "Pasha Yatırım Bankası A.Ş.",
    "Standard Chartered Yatırım Bankası Türk A.Ş.",
)


def _build_sum_if(items: tuple[str, ...], main_stmt: str, col: str = "amount_total") -> str:
    """Build a sumIf expression for a list of child_statement values."""
    escaped = ", ".join(f"'{s}'" for s in items)
    return (
        f"sumIf({col}, startsWith(main_statement, '{main_stmt}') "
        f"AND child_statement IN ({escaped}))"
    )


def _lc_select_columns() -> str:
    """Return the SELECT columns for LC calculation (on-balance + off-balance sheet)."""
    return f"""
        bank_name,
        {_build_sum_if(_LIQUID_ASSETS, '1. VARLIKLAR')} AS liquid_assets,
        {_build_sum_if(_SEMI_LIQUID_ASSETS, '1. VARLIKLAR')} AS semi_liquid_assets,
        {_build_sum_if(_ILLIQUID_ASSETS, '1. VARLIKLAR')} AS illiquid_assets,
        {_build_sum_if(_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS liquid_liabilities,
        {_build_sum_if(_SEMI_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS semi_liquid_liabilities,
        {_build_sum_if(_ILLIQUID_LIABILITIES_EQUITY, '2. YÜKÜMLÜLÜKLER')} AS illiquid_liabilities_equity,
        {_build_sum_if(_ILLIQUID_OBS, '3. NAZIM HESAPLAR')} AS illiquid_obs,
        {_build_sum_if(_SEMI_LIQUID_OBS, '3. NAZIM HESAPLAR')} AS semi_liquid_obs,
        sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
            AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS total_assets
    """


def _compute_lc_nonfat(row: dict) -> float | None:
    """Compute cat nonfat LC ratio (on-balance sheet only)."""
    ta = row["total_assets"]
    if not ta or ta == 0:
        return None
    numerator = (
        0.5 * (row["illiquid_assets"] + row["liquid_liabilities"])
        + 0.0 * (row["semi_liquid_assets"] + row["semi_liquid_liabilities"])
        - 0.5 * (row["liquid_assets"] + row["illiquid_liabilities_equity"])
    )
    return round(numerator / ta, 4)


def _compute_lc_fat(row: dict) -> float | None:
    """Compute cat fat LC ratio (includes off-balance sheet items)."""
    ta = row["total_assets"]
    if not ta or ta == 0:
        return None
    numerator = (
        0.5 * (row["illiquid_assets"] + row["liquid_liabilities"] + row["illiquid_obs"])
        + 0.0 * (row["semi_liquid_assets"] + row["semi_liquid_liabilities"] + row["semi_liquid_obs"])
        - 0.5 * (row["liquid_assets"] + row["illiquid_liabilities_equity"])
    )
    return round(numerator / ta, 4)


def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _aggregate_exclude() -> str:
    escaped = ", ".join(f"'{b}'" for b in _EXCLUDED_BANKS)
    return f"bank_name NOT IN ({escaped})"


def _get_konsol_only_banks(ch: Client) -> set[str]:
    """Return bank names that have KONSOLİDE data but NO SOLO data.

    Uses two lightweight DISTINCT queries + Python set difference,
    avoiding a heavy NOT IN subquery inside ClickHouse.
    """
    solo = ch.execute(
        "SELECT DISTINCT bank_name FROM tbb.financial_statements "
        "WHERE accounting_system LIKE '%SOLO%'"
    )
    konsol = ch.execute(
        "SELECT DISTINCT bank_name FROM tbb.financial_statements "
        "WHERE accounting_system LIKE '%KONSOLİDE%'"
    )
    solo_set = {r[0] for r in solo}
    konsol_set = {r[0] for r in konsol}
    return konsol_set - solo_set


def _acct_filter(
    accounting_system: str | None,
    escape: bool = True,
    konsol_only_banks: set[str] | None = None,
) -> str:
    """Return SQL filter for accounting system.

    When accounting_system is specified, filters to that system.
    When None (default), prefers SOLO but falls back to KONSOLİDE for banks
    that only have consolidated data (e.g. Ziraat, Halk, Vakıf, İş Bankası).

    Args:
        escape: Use %% for clickhouse_driver param substitution (True when
                query uses named params, False otherwise).
        konsol_only_banks: Pre-computed set of banks with KONSOLİDE-only data.
                           Required when accounting_system is None.
    """
    pct = "%%" if escape else "%"
    if accounting_system:
        return f"AND accounting_system LIKE '{pct}{accounting_system}{pct}'"
    # Prefer SOLO; fall back to KONSOLİDE for explicit list of banks
    if not konsol_only_banks:
        return f"AND accounting_system LIKE '{pct}SOLO{pct}'"
    escaped_banks = ", ".join(f"'{b}'" for b in konsol_only_banks)
    return (
        f"AND (accounting_system LIKE '{pct}SOLO{pct}'"
        f" OR (accounting_system LIKE '{pct}KONSOLİDE{pct}'"
        f" AND bank_name IN ({escaped_banks})))"
    )


async def get_liquidity_creation(
    ch: Client,
    redis: aioredis.Redis,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> list[dict]:
    """Calculate LC ratio per bank for a given period."""
    cache_key = f"liq:creation:v7:{year}:{month}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    konsol_only = _get_konsol_only_banks(ch) if not accounting_system else None

    query = f"""
        SELECT {_lc_select_columns()}
        FROM tbb.financial_statements FINAL
        WHERE year_id = %(year)s AND month_id = %(month)s
          AND {_aggregate_exclude()}
          {_acct_filter(accounting_system, konsol_only_banks=konsol_only)}
        GROUP BY bank_name
        HAVING total_assets > 0
        ORDER BY total_assets DESC
    """

    rows = ch.execute(query, {"year": year, "month": month})
    columns = [
        "bank_name", "liquid_assets", "semi_liquid_assets", "illiquid_assets",
        "liquid_liabilities", "semi_liquid_liabilities", "illiquid_liabilities_equity",
        "illiquid_obs", "semi_liquid_obs",
        "total_assets",
    ]

    data = []
    for r in rows:
        row = {col: _to_float(v) if i > 0 else v for i, (col, v) in enumerate(zip(columns, r))}
        ta = row["total_assets"]
        if any(abs(row[k]) > ta * 10 for k in columns[1:-1]):
            logger.warning("Skipping %s: data sanity check failed", row["bank_name"])
            continue
        lc_nonfat = _compute_lc_nonfat(row)
        lc_fat = _compute_lc_fat(row)
        if lc_nonfat is not None:
            row["lc_nonfat"] = lc_nonfat
            row["lc_fat"] = lc_fat
            row["lc_ratio"] = lc_nonfat  # backward compat
            data.append(row)

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data


async def get_liquidity_time_series(
    ch: Client,
    redis: aioredis.Redis,
    bank_name: str | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
    accounting_system: str | None = None,
) -> list[dict]:
    """LC time series — sector weighted average or single bank."""
    cache_key = f"liq:ts:v7:{bank_name}:{from_year}:{to_year}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    konsol_only = _get_konsol_only_banks(ch) if not accounting_system else None
    # Strip the leading "AND " from _acct_filter to use as a condition element
    acct_cond = _acct_filter(accounting_system, escape=True, konsol_only_banks=konsol_only).removeprefix("AND ")
    conditions = [_aggregate_exclude(), acct_cond]
    params: dict = {}

    if bank_name:
        conditions.append("bank_name = %(bank_name)s")
        params["bank_name"] = bank_name
    if from_year:
        conditions.append("year_id >= %(from_year)s")
        params["from_year"] = from_year
    if to_year:
        conditions.append("year_id <= %(to_year)s")
        params["to_year"] = to_year

    where = " AND ".join(conditions)

    if bank_name:
        query = f"""
            SELECT
                year_id, month_id,
                {_build_sum_if(_LIQUID_ASSETS, '1. VARLIKLAR')} AS liquid_assets,
                {_build_sum_if(_ILLIQUID_ASSETS, '1. VARLIKLAR')} AS illiquid_assets,
                {_build_sum_if(_SEMI_LIQUID_ASSETS, '1. VARLIKLAR')} AS semi_liquid_assets,
                {_build_sum_if(_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS liquid_liabilities,
                {_build_sum_if(_SEMI_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS semi_liquid_liabilities,
                {_build_sum_if(_ILLIQUID_LIABILITIES_EQUITY, '2. YÜKÜMLÜLÜKLER')} AS illiquid_liabilities_equity,
                {_build_sum_if(_ILLIQUID_OBS, '3. NAZIM HESAPLAR')} AS illiquid_obs,
                {_build_sum_if(_SEMI_LIQUID_OBS, '3. NAZIM HESAPLAR')} AS semi_liquid_obs,
                sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
                    AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS total_assets
            FROM tbb.financial_statements FINAL
            WHERE {where}
            GROUP BY year_id, month_id
            HAVING total_assets > 0
            ORDER BY year_id, month_id
        """
        rows = ch.execute(query, params)
        data = []
        for r in rows:
            vals = {
                "liquid_assets": _to_float(r[2]),
                "illiquid_assets": _to_float(r[3]),
                "semi_liquid_assets": _to_float(r[4]),
                "liquid_liabilities": _to_float(r[5]),
                "semi_liquid_liabilities": _to_float(r[6]),
                "illiquid_liabilities_equity": _to_float(r[7]),
                "illiquid_obs": _to_float(r[8]),
                "semi_liquid_obs": _to_float(r[9]),
                "total_assets": _to_float(r[10]),
            }
            lc_nonfat = _compute_lc_nonfat(vals)
            lc_fat = _compute_lc_fat(vals)
            if lc_nonfat is not None:
                data.append({
                    "year_id": r[0], "month_id": r[1],
                    "lc_nonfat": lc_nonfat, "lc_fat": lc_fat,
                    "lc_ratio": lc_nonfat,
                })
    else:
        query = f"""
            SELECT
                year_id, month_id,
                sum(la) AS liquid_assets,
                sum(ia) AS illiquid_assets,
                sum(sla) AS semi_liquid_assets,
                sum(ll) AS liquid_liabilities,
                sum(sll) AS semi_liquid_liabilities,
                sum(ile) AS illiquid_liabilities_equity,
                sum(iobs) AS illiquid_obs,
                sum(slobs) AS semi_liquid_obs,
                sum(ta) AS total_assets
            FROM (
                SELECT
                    bank_name, year_id, month_id,
                    {_build_sum_if(_LIQUID_ASSETS, '1. VARLIKLAR')} AS la,
                    {_build_sum_if(_ILLIQUID_ASSETS, '1. VARLIKLAR')} AS ia,
                    {_build_sum_if(_SEMI_LIQUID_ASSETS, '1. VARLIKLAR')} AS sla,
                    {_build_sum_if(_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS ll,
                    {_build_sum_if(_SEMI_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS sll,
                    {_build_sum_if(_ILLIQUID_LIABILITIES_EQUITY, '2. YÜKÜMLÜLÜKLER')} AS ile,
                    {_build_sum_if(_ILLIQUID_OBS, '3. NAZIM HESAPLAR')} AS iobs,
                    {_build_sum_if(_SEMI_LIQUID_OBS, '3. NAZIM HESAPLAR')} AS slobs,
                    sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
                        AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS ta
                FROM tbb.financial_statements FINAL
                WHERE {where}
                GROUP BY bank_name, year_id, month_id
                HAVING ta > 0
                  AND abs(la) <= ta * 10 AND abs(ia) <= ta * 10
                  AND abs(ll) <= ta * 10 AND abs(ile) <= ta * 10
                  AND abs(iobs) <= ta * 50 AND abs(slobs) <= ta * 50
            )
            GROUP BY year_id, month_id
            ORDER BY year_id, month_id
        """
        rows = ch.execute(query, params)
        data = []
        for r in rows:
            vals = {
                "liquid_assets": _to_float(r[2]),
                "illiquid_assets": _to_float(r[3]),
                "semi_liquid_assets": _to_float(r[4]),
                "liquid_liabilities": _to_float(r[5]),
                "semi_liquid_liabilities": _to_float(r[6]),
                "illiquid_liabilities_equity": _to_float(r[7]),
                "illiquid_obs": _to_float(r[8]),
                "semi_liquid_obs": _to_float(r[9]),
                "total_assets": _to_float(r[10]),
            }
            lc_nonfat = _compute_lc_nonfat(vals)
            lc_fat = _compute_lc_fat(vals)
            if lc_nonfat is not None:
                data.append({
                    "year_id": r[0], "month_id": r[1],
                    "lc_nonfat": lc_nonfat, "lc_fat": lc_fat,
                    "lc_ratio": lc_nonfat,
                })

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data


async def get_liquidity_by_group(
    ch: Client,
    redis: aioredis.Redis,
    pg: asyncpg.Pool,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> list[dict]:
    """LC weighted average by bank ownership group."""
    cache_key = f"liq:groups:v7:{year}:{month}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    # Get bank -> group mapping from PostgreSQL
    rows_pg = await pg.fetch(
        "SELECT bank_name, sub_bank_group FROM bank_info WHERE sub_bank_group IS NOT NULL"
    )
    bank_to_group: dict[str, str] = {}
    for r in rows_pg:
        bank_to_group[r["bank_name"]] = r["sub_bank_group"]

    # Get per-bank LC data
    bank_data = await get_liquidity_creation(ch, redis, year, month, accounting_system)

    # Aggregate by group
    groups: dict[str, dict] = {}
    for bd in bank_data:
        bname = bd["bank_name"]
        group = bank_to_group.get(bname)
        if not group:
            continue
        if group not in groups:
            groups[group] = {
                "nonfat_num": 0.0, "fat_num": 0.0,
                "total_assets_sum": 0.0, "bank_count": 0,
            }
        g = groups[group]
        ta = bd["total_assets"]
        nonfat_num = (
            0.5 * (bd["illiquid_assets"] + bd["liquid_liabilities"])
            - 0.5 * (bd["liquid_assets"] + bd["illiquid_liabilities_equity"])
        )
        fat_num = nonfat_num + 0.5 * bd.get("illiquid_obs", 0)
        g["nonfat_num"] += nonfat_num
        g["fat_num"] += fat_num
        g["total_assets_sum"] += ta
        g["bank_count"] += 1

    data = []
    for group_name, g in sorted(groups.items()):
        if g["total_assets_sum"] > 0:
            lc_nonfat = round(g["nonfat_num"] / g["total_assets_sum"], 4)
            lc_fat = round(g["fat_num"] / g["total_assets_sum"], 4)
            data.append({
                "group_name": group_name,
                "lc_nonfat": lc_nonfat,
                "lc_fat": lc_fat,
                "lc_ratio": lc_nonfat,
                "bank_count": g["bank_count"],
            })

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data


async def get_liquidity_decomposition(
    ch: Client,
    redis: aioredis.Redis,
    bank_name: str,
    year: int,
    month: int,
    accounting_system: str | None = None,
) -> dict | None:
    """LC decomposition for a single bank."""
    cache_key = f"liq:decomp:v7:{bank_name}:{year}:{month}:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    konsol_only = _get_konsol_only_banks(ch) if not accounting_system else None

    query = f"""
        SELECT {_lc_select_columns()}
        FROM tbb.financial_statements FINAL
        WHERE year_id = %(year)s AND month_id = %(month)s
          AND bank_name = %(bank_name)s
          {_acct_filter(accounting_system, konsol_only_banks=konsol_only)}
        GROUP BY bank_name
        HAVING total_assets > 0
    """

    rows = ch.execute(query, {"year": year, "month": month, "bank_name": bank_name})
    if not rows:
        return None

    r = rows[0]
    columns = [
        "bank_name", "liquid_assets", "semi_liquid_assets", "illiquid_assets",
        "liquid_liabilities", "semi_liquid_liabilities", "illiquid_liabilities_equity",
        "illiquid_obs", "semi_liquid_obs",
        "total_assets",
    ]
    row = {col: _to_float(v) if i > 0 else v for i, (col, v) in enumerate(zip(columns, r))}
    lc_nonfat = _compute_lc_nonfat(row)
    lc_fat = _compute_lc_fat(row)
    if lc_nonfat is None:
        return None

    ta = row["total_assets"]
    data = {
        "bank_name": row["bank_name"],
        "lc_nonfat": lc_nonfat,
        "lc_fat": lc_fat,
        "lc_ratio": lc_nonfat,
        "total_assets": ta,
        "components": {
            "liquid_assets": row["liquid_assets"],
            "semi_liquid_assets": row["semi_liquid_assets"],
            "illiquid_assets": row["illiquid_assets"],
            "liquid_liabilities": row["liquid_liabilities"],
            "semi_liquid_liabilities": row["semi_liquid_liabilities"],
            "illiquid_liabilities_equity": row["illiquid_liabilities_equity"],
            "illiquid_obs": row["illiquid_obs"],
            "semi_liquid_obs": row["semi_liquid_obs"],
        },
        "weighted_components": {
            "illiquid_assets_contrib": round(0.5 * row["illiquid_assets"] / ta, 4),
            "liquid_liabilities_contrib": round(0.5 * row["liquid_liabilities"] / ta, 4),
            "liquid_assets_drag": round(-0.5 * row["liquid_assets"] / ta, 4),
            "illiquid_liab_equity_drag": round(-0.5 * row["illiquid_liabilities_equity"] / ta, 4),
            "illiquid_obs_contrib": round(0.5 * row["illiquid_obs"] / ta, 4),
        },
    }

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data


# ---------------------------------------------------------------------------
# Group time series — Figure 2 from Çolak et al. (2024)
# ---------------------------------------------------------------------------
# Mapping sub_bank_group → paper's 3 main groups
_GROUP_MAP = {
    "Kamusal Sermayeli Mevduat Bankaları": "Kamusal",
    "Özel Sermayeli Mevduat Bankaları": "Özel",
    "Türkiye´de Kurulmuş Yabancı Sermayeli Bankalar": "Yabancı",
    "Türkiye´de Şube Açan Yabancı Sermayeli Bankalar": "Yabancı",
    "Tasarruf Mevduatı Sigorta Fonuna Devredilen Bankalar": "TMSF",
}


async def get_liquidity_group_time_series(
    ch: Client,
    redis: aioredis.Redis,
    pg: asyncpg.Pool,
    accounting_system: str | None = None,
) -> list[dict]:
    """LC time series by bank ownership group (Kamusal / Özel / Yabancı)."""
    cache_key = f"liq:grpts:v7:{accounting_system}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return cached

    # Bank → group mapping from PostgreSQL
    rows_pg = await pg.fetch(
        "SELECT bank_name, sub_bank_group FROM bank_info WHERE sub_bank_group IS NOT NULL"
    )
    bank_to_group: dict[str, str] = {}
    for r in rows_pg:
        mapped = _GROUP_MAP.get(r["sub_bank_group"])
        if mapped:
            bank_to_group[r["bank_name"]] = mapped

    # Per-bank, per-period LC from ClickHouse
    konsol_only = _get_konsol_only_banks(ch) if not accounting_system else None
    acct_cond = _acct_filter(accounting_system, escape=False, konsol_only_banks=konsol_only).removeprefix("AND ")
    conditions = [_aggregate_exclude(), acct_cond]
    where = " AND ".join(conditions)

    query = f"""
        SELECT
            bank_name, year_id, month_id,
            {_build_sum_if(_LIQUID_ASSETS, '1. VARLIKLAR')} AS la,
            {_build_sum_if(_ILLIQUID_ASSETS, '1. VARLIKLAR')} AS ia,
            {_build_sum_if(_LIQUID_LIABILITIES, '2. YÜKÜMLÜLÜKLER')} AS ll,
            {_build_sum_if(_ILLIQUID_LIABILITIES_EQUITY, '2. YÜKÜMLÜLÜKLER')} AS ile,
            sumIf(amount_total, startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS ta
        FROM tbb.financial_statements FINAL
        WHERE {where}
        GROUP BY bank_name, year_id, month_id
        HAVING ta > 0
          AND abs(la) <= ta * 10 AND abs(ia) <= ta * 10
          AND abs(ll) <= ta * 10 AND abs(ile) <= ta * 10
        ORDER BY year_id, month_id
    """
    rows = ch.execute(query)

    # Aggregate by group and period (asset-weighted)
    agg: dict[tuple[str, int, int], dict] = {}
    for r in rows:
        bname = r[0]
        group = bank_to_group.get(bname)
        if not group:
            continue
        year_id, month_id = r[1], r[2]
        la, ia, ll, ile, ta = [_to_float(v) for v in r[3:]]
        key = (group, year_id, month_id)
        if key not in agg:
            agg[key] = {"nonfat_num": 0.0, "ta_sum": 0.0}
        nonfat_num = 0.5 * (ia + ll) - 0.5 * (la + ile)
        agg[key]["nonfat_num"] += nonfat_num
        agg[key]["ta_sum"] += ta

    data = []
    for (group, year_id, month_id), g in sorted(
        agg.items(), key=lambda x: (x[0][1], x[0][2], x[0][0])
    ):
        if g["ta_sum"] > 0:
            data.append({
                "group_name": group,
                "year_id": year_id,
                "month_id": month_id,
                "lc_nonfat": round(g["nonfat_num"] / g["ta_sum"], 4),
            })

    await cache_set(redis, cache_key, data, CACHE_TTL, default=str)
    return data
