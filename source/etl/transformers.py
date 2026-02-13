"""Transform raw TBB API responses into DB-ready records."""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_hierarchy(record: dict) -> tuple[str, str]:
    """Extract accounting_system and main_statement from record hierarchy."""
    accounting_system = record.get("ROOT_TR_ADI", "")
    # Walk up PARENTS to find the main statement grouping
    parents = record.get("PARENTS", [])
    main_statement = parents[0].get("TR_ADI", "") if parents else ""
    return accounting_system, main_statement


def transform_financial(raw_records: list[dict]) -> list[dict]:
    """Transform raw financial API records into ClickHouse-ready dicts."""
    rows = []
    for record in raw_records:
        period = record.get("_period", {})
        stmt = record.get("_statement", {})

        accounting_system, main_statement = _build_hierarchy(record)

        rows.append({
            "accounting_system": accounting_system,
            "main_statement": main_statement or stmt.get("TR_ADI", ""),
            "child_statement": record.get("TR_ADI", ""),
            "bank_name": record.get("BANKA_ADI", ""),
            "year_id": int(period.get("YIL", 0)),
            "month_id": int(period.get("AY", 0)),
            "amount_tc": _safe_decimal(record.get("TP_DEGER")),
            "amount_fc": _safe_decimal(record.get("YP_DEGER")),
            "amount_total": _safe_decimal(record.get("TOPLAM")),
            "crawl_timestamp": datetime.now(),
        })

    logger.info("Transformed %d financial records", len(rows))
    return rows


def transform_regions(raw_records: list[dict]) -> list[dict]:
    """Transform raw regional API records into ClickHouse-ready dicts."""
    rows = []
    for record in raw_records:
        year_info = record.get("_year", {})
        param_info = record.get("_parameter", {})

        rows.append({
            "region": record.get("IL_BOLGE_KEY", record.get("BOLGE_ADI", "")),
            "metric": param_info.get("TR_ADI", record.get("PARAMETRE", "")),
            "year_id": int(year_info.get("YIL", 0)),
            "value": _safe_decimal(record.get("DEGER", 0)),
            "crawl_timestamp": datetime.now(),
        })

    logger.info("Transformed %d region records", len(rows))
    return rows


def transform_risk_center(raw_records: list[dict]) -> list[dict]:
    """Transform raw risk center API records into ClickHouse-ready dicts."""
    rows = []
    for record in raw_records:
        period = record.get("_period", {})
        report = record.get("_report", {})

        rows.append({
            "report_name": report.get("ADI", record.get("RAPOR_ADI", "")),
            "category": record.get("KATEGORI_ADI", ""),
            "person_count": _safe_int(record.get("TEKIL_KISI_SAYISI")),
            "quantity": _safe_int(record.get("ADET")),
            "amount": _safe_decimal(record.get("TUTAR")),
            "year_id": int(period.get("YIL", 0)),
            "month_id": int(period.get("AY", 0)),
            "crawl_timestamp": datetime.now(),
        })

    logger.info("Transformed %d risk center records", len(rows))
    return rows


def transform_bank_info(raw_data: dict) -> dict[str, list[dict]]:
    """Transform raw bank info into PostgreSQL-ready dicts.

    Returns dict with keys: bank_info, branch_info, atm_info, historical_events
    """
    result: dict[str, list[dict]] = {
        "bank_info": [],
        "branch_info": [],
        "atm_info": [],
        "historical_events": [],
    }

    banks = raw_data.get("banks", [])
    details = raw_data.get("details", [])

    for bank in banks:
        group = bank.get("_group", {})
        result["bank_info"].append({
            "bank_group": group.get("TR_ADI", ""),
            "sub_bank_group": group.get("ALT_GRUP_ADI", ""),
            "bank_name": bank.get("TR_ADI", bank.get("ADI", "")),
            "address": bank.get("ADRES", ""),
            "board_president": bank.get("YK_BASKANI", ""),
            "general_manager": bank.get("GENEL_MUDUR", ""),
            "phone_fax": bank.get("TELEFON_FAX", ""),
            "web_kep_address": bank.get("WEB_KEP", ""),
            "eft": bank.get("EFT", ""),
            "swift": bank.get("SWIFT", ""),
        })

    for detail in details:
        bank = detail.get("_bank", {})
        bank_name = bank.get("TR_ADI", bank.get("ADI", ""))

        # Branches
        for branch in detail.get("SUBELER", []):
            result["branch_info"].append({
                "bank_name": bank_name,
                "branch_name": branch.get("SUBE_ADI", ""),
                "address": branch.get("ADRES", ""),
                "district": branch.get("ILCE", ""),
                "city": branch.get("IL", ""),
                "phone": branch.get("TELEFON", ""),
                "fax": branch.get("FAX", ""),
                "opening_date": branch.get("ACILIS_TARIHI"),
            })

        # ATMs
        for atm in detail.get("ATMLER", []):
            result["atm_info"].append({
                "bank_name": bank_name,
                "branch_name": atm.get("SUBE_ADI", ""),
                "address": atm.get("ADRES", ""),
                "district": atm.get("ILCE", ""),
                "city": atm.get("IL", ""),
                "phone": atm.get("TELEFON", ""),
                "fax": atm.get("FAX", ""),
                "opening_date": atm.get("ACILIS_TARIHI"),
            })

        # Historical events
        history = detail.get("TARIHCE", {})
        if history:
            result["historical_events"].append({
                "bank_name": bank_name,
                "founding_date": history.get("KURULUS_TARIHI"),
                "historical_event": history.get("TARIHCE_METNI", ""),
            })

    logger.info(
        "Transformed bank info: %d banks, %d branches, %d ATMs, %d history records",
        len(result["bank_info"]),
        len(result["branch_info"]),
        len(result["atm_info"]),
        len(result["historical_events"]),
    )
    return result
