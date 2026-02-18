"""Panel Regression service — replicating Çolak et al. (2024) models.

Cross-sectional OLS on 2025/9 data:

Model 1 — Capital Adequacy → LC (Eq. 2):
  LC_i = α + β CapitalAdequacy_i + θ X_i + ε_i

Model 2 — LC → Bank Risk (Eq. 5):
  BankRisk_i = α + β LC_i + θ X_i + ε_i

Model 3 — State Ownership → LC (Eq. 4):
  LC_i = α + β State_i + θ X_i + ε_i

Where:
  - LC = liquidity creation (cat nonfat) / total assets
  - CapitalAdequacy = equity / total_assets - 0.08 (excess over 8% threshold)
  - BankRisk = Z-Score = (capital_ratio + ROA) / |ROA|
  - X = bank controls: BankSize (ln assets), ROA
"""

import json
import logging
import math
from decimal import Decimal

import numpy as np
import pandas as pd
import statsmodels.api as sm

import redis.asyncio as aioredis
from clickhouse_driver import Client

from db.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_TTL = 3600

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

# State-owned banks (kamusal sermayeli)
_STATE_BANKS = {
    "T.C. Ziraat Bankası A.Ş.",
    "Türkiye Cumhuriyeti Ziraat Bankası A.Ş.",
    "Türkiye Halk Bankası A.Ş.",
    "Türkiye Vakıflar Bankası T.A.O.",
}

# Private Turkish banks (özel sermayeli)
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


def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _build_panel_data(ch: Client, accounting_system: str | None = None) -> pd.DataFrame:
    """Build panel dataset from ClickHouse with all needed variables."""
    pct = "%%"
    acct = f"AND accounting_system LIKE '{pct}SOLO{pct}'"
    if accounting_system:
        acct = f"AND accounting_system LIKE '{pct}{accounting_system}{pct}'"

    excluded = ", ".join(f"'{b}'" for b in _EXCLUDED_BANKS)

    # Liquidity classification items (same as liquidity_service)
    query = f"""
        SELECT
            bank_name,
            year_id,
            month_id,
            -- Equity
            sumIf(amount_total,
                startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
                AND child_statement = 'XVI. ÖZKAYNAKLAR') AS equity,
            -- Total Assets
            sumIf(amount_total,
                startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement = 'XI. VARLIKLAR TOPLAMI') AS total_assets,
            -- Net Income
            sumIf(amount_total,
                (startsWith(main_statement, '4. GELİR-GİDER TABLOSU')
                 OR startsWith(main_statement, '5. KAR VEYA ZARAR'))
                AND child_statement = 'XXV. DÖNEM NET KARI/ZARARI (XIX+XXIV)') AS net_income,
            -- Net Interest Income
            sumIf(amount_total,
                (startsWith(main_statement, '4. GELİR-GİDER TABLOSU')
                 OR startsWith(main_statement, '5. KAR VEYA ZARAR'))
                AND child_statement = 'III. NET FAİZ GELİRİ/GİDERİ (I - II)') AS net_interest_income,
            -- Liquid Assets
            sumIf(amount_total,
                startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement IN (
                    '1.1 Nakit ve Nakit Benzerleri',
                    '1.2 Gerçeğe Uygun Değer Farkı Kar Zarara Yansıtılan FV',
                    '1.3 Gerçeğe Uygun Değer Farkı Diğer Kapsamlı Gelire Yansıtılan FV'
                )) AS liquid_assets,
            -- Semi-liquid Assets
            sumIf(amount_total,
                startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement IN (
                    '1.4 Türev Finansal Varlıklar',
                    '2.2 Kiralama İşlemlerinden Alacaklar',
                    '2.3 Faktoring Alacakları',
                    '2.4 İtfa Edilmiş Maliyeti ile Ölçülen Diğer Finansal Varlıklar',
                    'III.SATIŞ AMAÇ.ELDE TUTU.VE DURD.FAAL.İLİŞKİN DURAN VARL.(Net)',
                    'IV. ORTAKLIK YATIRIMLARI',
                    'VIII. CARİ VERGİ VARLIĞI',
                    'IX. ERTELENMİŞ VERGİ VARLIĞI'
                )) AS semi_liquid_assets,
            -- Illiquid Assets
            sumIf(amount_total,
                startsWith(main_statement, '1. VARLIKLAR')
                AND child_statement IN (
                    '2.1. Krediler',
                    'V. MADDİ DURAN VARLIKLAR(Net)',
                    'VI. MADDİ OLMAYAN DURAN VARLIKLAR(Net)',
                    'VII. YATIRIM AMAÇLI GAYRİMENKULLER (NET)',
                    'X. DİĞER AKTİFLER (Net)'
                )) AS illiquid_assets,
            -- Liquid Liabilities
            sumIf(amount_total,
                startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
                AND child_statement IN (
                    'I. MEVDUAT',
                    'II. ALINAN KREDİLER',
                    'III. PARA PİYASALARINA BORÇLAR',
                    'V. FONLAR',
                    'VI. GERÇEĞE UYGUN DEĞER FARKI KAR ZARARA YANSITILAN FİNANSAL YÜKÜMLÜLÜKLER'
                )) AS liquid_liabilities,
            -- Illiquid Liabilities + Equity
            sumIf(amount_total,
                startsWith(main_statement, '2. YÜKÜMLÜLÜKLER')
                AND child_statement IN (
                    'IV. İHRAÇ EDİLEN MENKUL KIYMETLER (Net)',
                    'IX. KİRALAMA İŞLEMLERİNDEN YÜKÜMLÜLÜKLER (Net)',
                    'XIV. SERMAYE BENZERİ BORÇLANMA ARAÇLARI',
                    'XVI. ÖZKAYNAKLAR'
                )) AS illiquid_liabilities_equity
        FROM tbb.financial_statements
        WHERE bank_name NOT IN ({excluded})
            {acct}
            AND year_id = 2025 AND month_id = 9
        GROUP BY bank_name, year_id, month_id
        HAVING total_assets > 0
        ORDER BY bank_name
    """
    rows = ch.execute(query)

    records = []
    for r in rows:
        ta = _to_float(r[4])
        if ta == 0:
            continue
        equity = _to_float(r[3])
        net_income = _to_float(r[5])
        liq_a = _to_float(r[7])
        semi_a = _to_float(r[8])
        illiq_a = _to_float(r[9])
        liq_l = _to_float(r[10])
        illiq_l_eq = _to_float(r[11])

        roa = net_income / ta
        capital_ratio = equity / ta
        lc_nonfat_num = (
            0.5 * (illiq_a + liq_l)
            + 0.0 * (semi_a)
            - 0.5 * (liq_a + illiq_l_eq)
        )
        lc_nonfat = lc_nonfat_num / ta

        records.append({
            "bank_name": r[0],
            "year_id": r[1],
            "month_id": r[2],
            "period": f"{r[1]}_{r[2]}",
            "equity": equity,
            "total_assets": ta,
            "net_income": net_income,
            "roa": roa,
            "capital_ratio": capital_ratio,
            "capital_adequacy": capital_ratio - 0.08,  # excess over 8%
            "bank_size": math.log(ta) if ta > 0 else 0.0,
            "lc_nonfat": lc_nonfat,
            "state": 1 if r[0] in _STATE_BANKS else 0,
            "nim": _to_float(r[6]) / ta,
        })

    df = pd.DataFrame(records)
    return df


def _compute_zscore_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add z_score column. Single period: use |ROA| as denominator."""
    df = df.copy()
    df["z_score"] = df.apply(
        lambda r: (r["capital_ratio"] + r["roa"]) / (abs(r["roa"]) if r["roa"] != 0 else 1e-6),
        axis=1,
    )
    return df


def _run_pooled_ols(df: pd.DataFrame, y_col: str, x_cols: list[str]) -> dict:
    """Run pooled OLS (no fixed effects) — for state ownership model."""
    panel = df[[y_col] + x_cols].dropna()
    if panel.empty or len(panel) < len(x_cols) + 2:
        return {"error": "Yetersiz gozlem sayisi"}

    y = panel[y_col]
    X = sm.add_constant(panel[x_cols])

    try:
        model = sm.OLS(y, X).fit()
    except Exception as e:
        logger.error("Pooled OLS failed: %s", e)
        return {"error": str(e)}

    coefficients = []
    for i, col in enumerate(X.columns):
        coefficients.append({
            "variable": col if col != "const" else "Sabit",
            "coefficient": float(round(model.params.iloc[i], 6)),
            "std_error": float(round(model.bse.iloc[i], 6)),
            "t_stat": float(round(model.tvalues.iloc[i], 4)),
            "p_value": float(round(model.pvalues.iloc[i], 4)),
            "significant": bool(model.pvalues.iloc[i] < 0.05),
        })

    return {
        "coefficients": coefficients,
        "r_squared": float(round(model.rsquared, 4)),
        "adj_r_squared": float(round(model.rsquared_adj, 4)),
        "n_obs": int(len(panel)),
        "n_entities": int(df["bank_name"].nunique()) if "bank_name" in df.columns else None,
        "f_stat": float(round(model.fvalue, 4)) if model.fvalue else None,
        "f_pvalue": float(round(model.f_pvalue, 4)) if model.f_pvalue else None,
    }


async def run_panel_regressions(
    ch: Client,
    redis: aioredis.Redis,
    accounting_system: str | None = None,
) -> dict:
    """Run all panel regression models from Çolak et al. (2024)."""
    cache_key = f"panel:regressions:{accounting_system or 'default'}"
    cached = await cache_get(redis, cache_key)
    if cached:
        return json.loads(cached)

    df = _build_panel_data(ch, accounting_system)
    if df.empty:
        return {"error": "Panel verisi olusturulamadi"}

    df = _compute_zscore_column(df)

    # Remove extreme outliers (winsorize at 1st/99th percentile)
    for col in ["lc_nonfat", "z_score", "capital_adequacy", "roa", "bank_size"]:
        if col in df.columns:
            q01 = df[col].quantile(0.01)
            q99 = df[col].quantile(0.99)
            df[col] = df[col].clip(q01, q99)

    # --- Model 1: Capital Adequacy → LC (Eq. 2) ---
    model1 = _run_pooled_ols(
        df, y_col="lc_nonfat",
        x_cols=["capital_adequacy", "bank_size", "roa"],
    )

    # --- Model 2: LC → Bank Risk / Z-Score (Eq. 5) ---
    model2 = _run_pooled_ols(
        df, y_col="z_score",
        x_cols=["lc_nonfat", "bank_size", "roa"],
    )

    # --- Model 3: State Ownership → LC (Eq. 4) ---
    model3 = _run_pooled_ols(
        df, y_col="lc_nonfat",
        x_cols=["state", "bank_size", "roa"],
    )

    # --- Panel descriptive stats ---
    desc_cols = ["lc_nonfat", "z_score", "capital_adequacy", "roa", "bank_size", "state"]
    desc = {}
    for col in desc_cols:
        if col in df.columns:
            desc[col] = {
                "mean": float(round(df[col].mean(), 6)),
                "std": float(round(df[col].std(), 6)),
                "min": float(round(df[col].min(), 6)),
                "max": float(round(df[col].max(), 6)),
                "count": int(df[col].count()),
            }

    # --- Bank-level data for scatter chart ---
    bank_data = []
    for _, row in df.iterrows():
        bank_data.append({
            "bank_name": row["bank_name"],
            "capital_adequacy": float(round(row["capital_adequacy"], 6)),
            "lc_nonfat": float(round(row["lc_nonfat"], 6)),
            "z_score": float(round(row["z_score"], 4)),
            "roa": float(round(row["roa"], 6)),
            "bank_size": float(round(row["bank_size"], 4)),
            "state": int(row["state"]),
            "bank_group": _get_bank_group(row["bank_name"]),
        })

    result = {
        "models": {
            "capital_adequacy_lc": {
                "title": "Sermaye Yeterliligi → Likidite Yaratimi (Eq. 2)",
                "dependent": "LC (Cat Nonfat)",
                "method": "OLS",
                **model1,
            },
            "lc_bank_risk": {
                "title": "Likidite Yaratimi → Banka Riski (Eq. 5)",
                "dependent": "Z-Score (Banka Riski)",
                "method": "OLS",
                **model2,
            },
            "state_ownership_lc": {
                "title": "Kamu Sahipligi → Likidite Yaratimi (Eq. 4)",
                "dependent": "LC (Cat Nonfat)",
                "method": "OLS",
                **model3,
            },
        },
        "descriptive_stats": desc,
        "panel_info": {
            "n_banks": int(df["bank_name"].nunique()),
            "n_periods": 1,
            "total_obs": int(len(df)),
            "periods": ["2025_9"],
        },
        "bank_data": bank_data,
    }

    await cache_set(redis, cache_key, json.dumps(result), ttl=CACHE_TTL)
    return result
