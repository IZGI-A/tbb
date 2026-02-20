"""Panel Regression service — replicating Çolak et al. (2024) models.

Panel data regression with fixed effects (LSDV approach):

Model 1 — Eq. (2): Capital Adequacy → LC
  LC_it = β CapitalAdequacy_{it-1} + θ X_{it-1} + δ_i + γ_t + ε_it

Model 2 — Eq. (3): Competition → LC
  LC_it = β Competition_{t-1} + θ X_{it-1} + δ_i + ε_it

Model 3 — Eq. (4): State Ownership → LC
  LC_it = β State_i + θ X_{it-1} + γ_t + ε_it

Model 4 — Eq. (5): LC → Bank Risk
  BankRisk_it = β LC_{it-1} + θ X_{it-1} + δ_i + γ_t + ε_it

Where:
  - LC = liquidity creation (cat nonfat) / total assets
  - CapitalAdequacy = equity / total_assets - 0.08
  - Competition = 1 / HHI (inverse Herfindahl-Hirschman Index)
  - State = binary (1 = state-owned, 0 = otherwise)
  - BankRisk = Z-Score = (capital_ratio + ROA) / σ(ROA)
  - X = bank controls: BankSize (ln assets), ROA
  - δ_i = bank fixed effects, γ_t = time fixed effects
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
    "Ziraat Dinamik Banka A.Ş. (dijital banka)",
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
    """Build multi-period panel dataset from ClickHouse."""
    pct = "%%"
    acct = f"AND accounting_system LIKE '{pct}SOLO{pct}'"
    if accounting_system:
        acct = f"AND accounting_system LIKE '{pct}{accounting_system}{pct}'"

    excluded = ", ".join(f"'{b}'" for b in _EXCLUDED_BANKS)

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
        ORDER BY bank_name, year_id, month_id
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
            "period_num": r[1] * 100 + r[2],
            "equity": equity,
            "total_assets": ta,
            "net_income": net_income,
            "roa": roa,
            "capital_ratio": capital_ratio,
            "capital_adequacy": capital_ratio - 0.08,
            "bank_size": math.log(ta) if ta > 0 else 0.0,
            "lc_nonfat": lc_nonfat,
            "state": 1 if r[0] in _STATE_BANKS else 0,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values(["bank_name", "period_num"]).reset_index(drop=True)
    return df


def _add_competition(df: pd.DataFrame) -> pd.DataFrame:
    """Add Competition = 1/HHI per period (bank-invariant, time-varying)."""
    df = df.copy()
    comps = {}
    for period in df["period"].unique():
        mask = df["period"] == period
        total_assets = df.loc[mask, "total_assets"].sum()
        if total_assets == 0:
            comps[period] = np.nan
            continue
        shares = df.loc[mask, "total_assets"] / total_assets
        hhi = (shares ** 2).sum()
        comps[period] = 1.0 / hhi if hhi > 0 else np.nan
    df["competition"] = df["period"].map(comps)
    return df


def _add_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Add Z-Score = (capital_ratio + ROA) / σ(ROA) per bank."""
    df = df.copy()
    if df["period"].nunique() > 1:
        roa_std = df.groupby("bank_name")["roa"].transform("std")
        roa_std = roa_std.replace(0, 1e-6).fillna(1e-6)
        df["z_score"] = (df["capital_ratio"] + df["roa"]) / roa_std
    else:
        denom = df["roa"].abs().replace(0, 1e-6)
        df["z_score"] = (df["capital_ratio"] + df["roa"]) / denom
    return df


def _add_lags(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Add t-1 lagged variables within each bank."""
    df = df.sort_values(["bank_name", "period_num"]).copy()
    for col in cols:
        df[f"L_{col}"] = df.groupby("bank_name")[col].shift(1)
    return df


def _run_panel_fe(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    entity_fe: bool = True,
    time_fe: bool = True,
) -> dict:
    """Run panel regression with fixed effects using LSDV + clustered SEs."""
    required = [y_col] + x_cols + ["bank_name", "period"]
    panel = df[required].dropna().copy()

    if panel.empty or len(panel) < len(x_cols) + 2:
        return {"error": "Yetersiz gozlem sayisi"}

    y = panel[y_col]
    X_data = panel[x_cols].copy()

    if entity_fe and panel["bank_name"].nunique() > 1:
        entity_d = pd.get_dummies(
            panel["bank_name"], prefix="bnk", drop_first=True, dtype=float,
        )
        X_data = pd.concat([X_data, entity_d], axis=1)

    if time_fe and panel["period"].nunique() > 1:
        time_d = pd.get_dummies(
            panel["period"], prefix="prd", drop_first=True, dtype=float,
        )
        X_data = pd.concat([X_data, time_d], axis=1)

    X_data = sm.add_constant(X_data)

    try:
        if entity_fe and panel["bank_name"].nunique() > 1:
            model = sm.OLS(y, X_data).fit(
                cov_type="cluster",
                cov_kwds={"groups": panel["bank_name"].values},
            )
        else:
            model = sm.OLS(y, X_data).fit()
    except Exception as e:
        logger.error("Panel FE regression failed: %s", e)
        return {"error": str(e)}

    # Extract only main variable coefficients (not dummies)
    coefficients = []
    for col in x_cols:
        if col in X_data.columns:
            idx = list(X_data.columns).index(col)
            coefficients.append({
                "variable": col,
                "coefficient": float(round(model.params.iloc[idx], 6)),
                "std_error": float(round(model.bse.iloc[idx], 6)),
                "t_stat": float(round(model.tvalues.iloc[idx], 4)),
                "p_value": float(round(model.pvalues.iloc[idx], 4)),
                "significant": bool(model.pvalues.iloc[idx] < 0.05),
            })

    # Compute within R² for entity FE models
    r2 = float(round(model.rsquared, 4))
    if entity_fe and panel["bank_name"].nunique() > 1:
        y_demean = y - y.groupby(panel["bank_name"]).transform("mean")
        ss_within = (y_demean ** 2).sum()
        if ss_within > 0:
            r2 = float(round(1.0 - model.ssr / ss_within, 4))

    try:
        f_stat = float(round(model.fvalue, 4))
        f_pvalue = float(round(model.f_pvalue, 4))
    except Exception:
        f_stat = None
        f_pvalue = None

    return {
        "coefficients": coefficients,
        "r_squared": r2,
        "adj_r_squared": float(round(model.rsquared_adj, 4)),
        "n_obs": int(len(panel)),
        "n_entities": int(panel["bank_name"].nunique()),
        "n_periods": int(panel["period"].nunique()),
        "f_stat": f_stat,
        "f_pvalue": f_pvalue,
    }


def _run_pooled_ols(df: pd.DataFrame, y_col: str, x_cols: list[str]) -> dict:
    """Run pooled OLS — cross-sectional fallback for single period."""
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

    df = _add_competition(df)
    df = _add_zscore(df)

    # Winsorize at 1st/99th percentile
    for col in ["lc_nonfat", "z_score", "capital_adequacy", "roa", "bank_size", "competition"]:
        if col in df.columns:
            q01 = df[col].quantile(0.01)
            q99 = df[col].quantile(0.99)
            df[col] = df[col].clip(q01, q99)

    n_periods = df["period"].nunique()
    periods = df.sort_values("period_num")["period"].unique().tolist()

    if n_periods >= 2:
        # --- Multi-period panel: use lags and fixed effects ---
        df = _add_lags(df, [
            "capital_adequacy", "bank_size", "roa", "lc_nonfat", "competition",
        ])

        # Model 1 — Eq. (2): Capital Adequacy → LC
        model1 = _run_panel_fe(
            df, y_col="lc_nonfat",
            x_cols=["L_capital_adequacy", "L_bank_size", "L_roa"],
            entity_fe=True, time_fe=True,
        )

        # Model 2 — Eq. (3): Competition → LC
        model2 = _run_panel_fe(
            df, y_col="lc_nonfat",
            x_cols=["L_competition", "L_bank_size", "L_roa"],
            entity_fe=True, time_fe=False,
        )

        # Model 3 — Eq. (4): State Ownership → LC
        model3 = _run_panel_fe(
            df, y_col="lc_nonfat",
            x_cols=["state", "L_bank_size", "L_roa"],
            entity_fe=False, time_fe=True,
        )

        # Model 4 — Eq. (5): LC → Bank Risk
        model4 = _run_panel_fe(
            df, y_col="z_score",
            x_cols=["L_lc_nonfat", "L_bank_size", "L_roa"],
            entity_fe=True, time_fe=True,
        )

        m1_method = "Panel FE (Banka + Zaman)"
        m2_method = "Panel FE (Banka)"
        m3_method = "Panel FE (Zaman)"
        m4_method = "Panel FE (Banka + Zaman)"
    else:
        # --- Single period: cross-sectional OLS ---
        model1 = _run_pooled_ols(
            df, "lc_nonfat", ["capital_adequacy", "bank_size", "roa"],
        )
        model2 = _run_pooled_ols(
            df, "lc_nonfat", ["competition", "bank_size", "roa"],
        )
        model3 = _run_pooled_ols(
            df, "lc_nonfat", ["state", "bank_size", "roa"],
        )
        model4 = _run_pooled_ols(
            df, "z_score", ["lc_nonfat", "bank_size", "roa"],
        )

        m1_method = "OLS (Kesitsel)"
        m2_method = "OLS (Kesitsel)"
        m3_method = "OLS (Kesitsel)"
        m4_method = "OLS (Kesitsel)"

    # --- Descriptive statistics ---
    desc_cols = [
        "lc_nonfat", "z_score", "capital_adequacy", "roa",
        "bank_size", "state", "competition",
    ]
    desc = {}
    for col in desc_cols:
        if col in df.columns:
            s = df[col].dropna()
            if not s.empty:
                desc[col] = {
                    "mean": float(round(s.mean(), 6)),
                    "std": float(round(s.std(), 6)),
                    "min": float(round(s.min(), 6)),
                    "max": float(round(s.max(), 6)),
                    "count": int(s.count()),
                }

    # --- Bank-level data for scatter chart (latest period) ---
    latest_period_num = df["period_num"].max()
    latest_df = df[df["period_num"] == latest_period_num]
    bank_data = []
    for _, row in latest_df.iterrows():
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
                "title": "Sermaye Yeterliligi \u2192 Likidite Yaratimi (Eq. 2)",
                "dependent": "LC (Cat Nonfat)",
                "method": m1_method,
                "equation": "LC_it = \u03b2\u00b7CapAdequacy_{it-1} + \u03b8X_{it-1} + \u03b4_i + \u03b3_t + \u03b5_it",
                "fixed_effects": "Banka + Zaman",
                **model1,
            },
            "competition_lc": {
                "title": "Rekabet \u2192 Likidite Yaratimi (Eq. 3)",
                "dependent": "LC (Cat Nonfat)",
                "method": m2_method,
                "equation": "LC_it = \u03b2\u00b7Competition_{t-1} + \u03b8X_{it-1} + \u03b4_i + \u03b5_it",
                "fixed_effects": "Banka",
                **model2,
            },
            "state_ownership_lc": {
                "title": "Kamu Sahipligi \u2192 Likidite Yaratimi (Eq. 4)",
                "dependent": "LC (Cat Nonfat)",
                "method": m3_method,
                "equation": "LC_it = \u03b2\u00b7State_i + \u03b8X_{it-1} + \u03b3_t + \u03b5_it",
                "fixed_effects": "Zaman",
                **model3,
            },
            "lc_bank_risk": {
                "title": "Likidite Yaratimi \u2192 Banka Riski (Eq. 5)",
                "dependent": "Z-Score (Banka Riski)",
                "method": m4_method,
                "equation": "Risk_it = \u03b2\u00b7LC_{it-1} + \u03b8X_{it-1} + \u03b4_i + \u03b3_t + \u03b5_it",
                "fixed_effects": "Banka + Zaman",
                **model4,
            },
        },
        "descriptive_stats": desc,
        "panel_info": {
            "n_banks": int(df["bank_name"].nunique()),
            "n_periods": n_periods,
            "total_obs": int(len(df)),
            "periods": periods,
        },
        "bank_data": bank_data,
    }

    await cache_set(redis, cache_key, json.dumps(result), ttl=CACHE_TTL)
    return result
