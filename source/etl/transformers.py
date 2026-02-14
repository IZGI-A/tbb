"""Transform scraped HTML table data into DB-ready records."""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "" or value == "-":
        return None
    try:
        # Clean Turkish number format: 1.234.567,89 → 1234567.89
        text = str(value).strip()
        text = text.replace(".", "").replace(",", ".")
        text = re.sub(r"[^\d.\-]", "", text)
        if not text:
            return None
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None or value == "" or value == "-":
        return None
    try:
        text = str(value).strip()
        text = text.replace(".", "").replace(",", "")
        text = re.sub(r"[^\d\-]", "", text)
        if not text:
            return None
        return int(text)
    except (ValueError, TypeError):
        return None


def _first_of(*keys, record: dict, default: Any = "") -> Any:
    """Return the first non-empty value found for the given keys in *record*."""
    for k in keys:
        val = record.get(k)
        if val is not None and val != "":
            return val
    return default


def transform_financial(raw_records: list[dict]) -> list[dict]:
    """Transform scraped financial table rows into ClickHouse-ready dicts.

    Handles both the old flat-table format and the new pivot-grid format
    where records have keys like 'Ana Kalem', 'TP', 'YP', 'Toplam'.
    """
    rows = []
    for record in raw_records:
        accounting_system = _first_of(
            "Muhasebe Sistemi", "Hesap Sistemi", "_statement_text",
            record=record,
        )
        main_statement = _first_of(
            "Ana Kalem", "Bilanço Kalemi", "row_text", "_row_text", "col_0",
            record=record,
        )
        child_statement = _first_of(
            "Alt Kalem", "Kalem", "col_1",
            record=record,
        )
        bank_name = _first_of(
            "Banka", "Banka Adı", "col_2",
            record=record,
        )

        # Amount columns — try pivot field names first, then legacy headers
        amount_tc = _safe_decimal(
            _first_of("TP", "TP Tutar", "TL", "col_3", record=record, default=None)
        )
        amount_fc = _safe_decimal(
            _first_of("YP", "YP Tutar", "col_4", record=record, default=None)
        )
        amount_total = _safe_decimal(
            _first_of("Toplam", "TOPLAM", "col_5", record=record, default=None)
        )

        # If only a single unnamed value field exists (value_0), treat as total
        if amount_total is None and amount_tc is None and amount_fc is None:
            amount_total = _safe_decimal(
                _first_of("value_0", "value", record=record, default=None)
            )

        rows.append({
            "accounting_system": accounting_system,
            "main_statement": main_statement,
            "child_statement": child_statement,
            "bank_name": bank_name,
            "year_id": int(record.get("_year_id", 0)),
            "month_id": int(record.get("_month_id", 0)),
            "amount_tc": amount_tc,
            "amount_fc": amount_fc,
            "amount_total": amount_total,
            "crawl_timestamp": datetime.now(),
        })

    logger.info("Transformed %d financial records", len(rows))
    return rows


def transform_regions(raw_records: list[dict]) -> list[dict]:
    """Transform scraped regional table rows into ClickHouse-ready dicts."""
    rows = []
    for record in raw_records:
        region = _first_of(
            "Bölge", "İl", "Bolge", "col_0",
            record=record,
        )
        metric = _first_of(
            "_parameter_text", "Parametre", "Metrik",
            record=record,
        )
        value = _safe_decimal(
            _first_of(
                "Değer", "Deger", "Toplam", "value_0", "value", "col_1",
                record=record, default=None,
            )
        )

        rows.append({
            "region": region,
            "metric": metric,
            "year_id": int(record.get("_year_id", 0)),
            "value": value,
            "crawl_timestamp": datetime.now(),
        })

    logger.info("Transformed %d region records", len(rows))
    return rows


def transform_risk_center(raw_records: list[dict]) -> list[dict]:
    """Transform scraped risk center table rows into ClickHouse-ready dicts."""
    rows = []
    for record in raw_records:
        report_name = _first_of(
            "_report_text", "Rapor Adı", "Rapor",
            record=record,
        )
        category = _first_of(
            "Kategori", "col_0",
            record=record,
        )
        person_count = _safe_int(
            _first_of(
                "Tekil Kişi Sayısı", "Kişi Sayısı", "col_1",
                record=record, default=None,
            )
        )
        quantity = _safe_int(
            _first_of("Adet", "col_2", record=record, default=None)
        )
        amount = _safe_decimal(
            _first_of(
                "Tutar", "Toplam", "value_0", "value", "col_3",
                record=record, default=None,
            )
        )

        rows.append({
            "report_name": report_name,
            "category": category,
            "person_count": person_count,
            "quantity": quantity,
            "amount": amount,
            "year_id": int(record.get("_year_id", 0)),
            "month_id": int(record.get("_month_id", 0)),
            "crawl_timestamp": datetime.now(),
        })

    logger.info("Transformed %d risk center records", len(rows))
    return rows


def transform_bank_info(raw_data: dict) -> dict[str, list[dict]]:
    """Transform scraped bank data into PostgreSQL-ready dicts.

    NOTE: The bank info page has been removed from TBB verisistemi.
    This function is kept for backwards compatibility but will receive
    empty input from the disabled BankInfoScraper.
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
        result["bank_info"].append({
            "bank_group": bank.get("Grup", bank.get("col_0", "")),
            "sub_bank_group": bank.get("Alt Grup", bank.get("col_1", "")),
            "bank_name": bank.get("Banka Adı", bank.get("Banka", bank.get("col_2", ""))),
            "address": bank.get("Adres", bank.get("col_3", "")),
            "board_president": bank.get("YK Başkanı", bank.get("col_4", "")),
            "general_manager": bank.get("Genel Müdür", bank.get("col_5", "")),
            "phone_fax": bank.get("Telefon/Fax", bank.get("col_6", "")),
            "web_kep_address": bank.get("Web/KEP", bank.get("col_7", "")),
            "eft": bank.get("EFT", bank.get("col_8", "")),
            "swift": bank.get("SWIFT", bank.get("col_9", "")),
        })

    for detail in details:
        bank_row = detail.get("_bank_row", {})
        bank_name = bank_row.get("Banka Adı", bank_row.get("Banka", bank_row.get("col_2", "")))
        info = detail.get("info", {})

        for branch in detail.get("branches", []):
            result["branch_info"].append({
                "bank_name": bank_name,
                "branch_name": branch.get("Şube Adı", branch.get("Sube", branch.get("col_0", ""))),
                "address": branch.get("Adres", branch.get("col_1", "")),
                "district": branch.get("İlçe", branch.get("Ilce", branch.get("col_2", ""))),
                "city": branch.get("İl", branch.get("Il", branch.get("col_3", ""))),
                "phone": branch.get("Telefon", branch.get("col_4", "")),
                "fax": branch.get("Fax", branch.get("col_5", "")),
                "opening_date": branch.get("Açılış Tarihi", branch.get("col_6")),
            })

        for atm in detail.get("atms", []):
            result["atm_info"].append({
                "bank_name": bank_name,
                "branch_name": atm.get("Şube Adı", atm.get("col_0", "")),
                "address": atm.get("Adres", atm.get("col_1", "")),
                "district": atm.get("İlçe", atm.get("col_2", "")),
                "city": atm.get("İl", atm.get("col_3", "")),
                "phone": atm.get("Telefon", atm.get("col_4", "")),
                "fax": atm.get("Fax", atm.get("col_5", "")),
                "opening_date": atm.get("Açılış Tarihi", atm.get("col_6")),
            })

        history = detail.get("history", {})
        history_text = history.get("text", "")
        if history_text or info:
            founding = info.get("Kuruluş Tarihi", info.get("Kurulus Tarihi"))
            result["historical_events"].append({
                "bank_name": bank_name,
                "founding_date": founding,
                "historical_event": history_text or info.get("Tarihçe", ""),
            })

    logger.info(
        "Transformed bank info: %d banks, %d branches, %d ATMs, %d history records",
        len(result["bank_info"]),
        len(result["branch_info"]),
        len(result["atm_info"]),
        len(result["historical_events"]),
    )
    return result
