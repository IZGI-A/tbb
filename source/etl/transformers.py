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
    # Handle numeric types directly (e.g. from API responses)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
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


def _parse_date(text: Any) -> str | None:
    """Parse Turkish date formats (dd.mm.yyyy, dd/mm/yyyy) to ISO yyyy-mm-dd."""
    if text is None or text == "" or text == "-":
        return None
    s = str(text).strip()
    for sep in (".", "/", "-"):
        parts = s.split(sep)
        if len(parts) == 3:
            d, m, y = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if d.isdigit() and m.isdigit() and y.isdigit() and len(y) == 4:
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return None


def _fix_encoding(text: str) -> str:
    """Fix double UTF-8 encoding (UTF-8 bytes misread as Latin-1).

    Example: "Ä°brazÄ±nda" → "İbrazında"
    """
    if not text or not isinstance(text, str):
        return text
    try:
        fixed = text.encode("latin-1").decode("utf-8")
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


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
        accounting_system = (_first_of(
            "Muhasebe Sistemi", "Hesap Sistemi", "_statement_text",
            record=record,
        ) or "").strip()
        main_statement = _first_of(
            "Ana Kalem", "Bilanço Kalemi", "row_text", "_row_text", "col_0",
            record=record,
        )
        child_statement = _first_of(
            "Alt Kalem", "Kalem", "col_1",
            record=record,
        )
        bank_name = (_first_of(
            "Banka", "Banka Adı", "col_2",
            record=record,
        ) or "").strip()

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
        report_name = _fix_encoding(_first_of(
            "_report_text", "Rapor Adı", "Rapor",
            record=record,
        ))
        category = _fix_encoding(_first_of(
            "Kategori", "col_0",
            record=record,
        ))
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


def _transform_branch_row(row: dict, fallback_bank: str = "") -> dict:
    """Map a scraped branch/ATM row to DB-ready dict."""
    bank_name = _first_of(
        "Banka", "Banka Adı", "col_0",
        record=row,
    ) or fallback_bank
    return {
        "bank_name": bank_name,
        "branch_name": _first_of(
            "Şube Adı", "Şube", "Sube Adi", "Sube", "col_1",
            record=row,
        ),
        "address": _first_of("Adres", "col_2", record=row),
        "district": _first_of("İlçe", "Ilce", "col_3", record=row),
        "city": _first_of("Şehir", "İl", "Il", "col_4", record=row),
        "phone": _first_of("Telefon", "col_5", record=row),
        "fax": _first_of("Faks", "Fax", "col_6", record=row),
        "opening_date": _parse_date(
            _first_of(
                "Açılış Tarihi", "Açılış", "Acilis Tarihi", "col_7",
                record=row, default=None,
            )
        ),
    }


def transform_bank_info(raw_data: dict) -> dict[str, list[dict]]:
    """Transform scraped bank data into PostgreSQL-ready dicts.

    Handles the flat format from the new tbb.org.tr scraper:
      {"banks": [...], "branches": [...], "atms": [...]}
    """
    result: dict[str, list[dict]] = {
        "bank_info": [],
        "branch_info": [],
        "atm_info": [],
        "historical_events": [],
    }

    # --- Bank list ---
    for bank in raw_data.get("banks", []):
        result["bank_info"].append({
            "bank_group": _first_of(
                "bank_group", "Grup", "col_0", record=bank,
            ),
            "sub_bank_group": _first_of(
                "sub_bank_group", "Alt Grup", "col_1", record=bank,
            ),
            "bank_name": _first_of(
                "Banka Adı", "Banka", "col_2", record=bank,
            ),
            "address": _first_of("Adres", "col_3", record=bank),
            "board_president": _first_of(
                "Y.K. Başkanı", "YK Başkanı", "YK Baskani", "col_4",
                record=bank,
            ),
            "general_manager": _first_of(
                "Genel Müdür", "Genel Mudur", "col_5", record=bank,
            ),
            "phone_fax": _first_of("Telefon/Fax", "col_6", record=bank),
            "web_kep_address": _first_of(
                "Web Adresi/KEP Adresleri", "Web/KEP", "col_7",
                record=bank,
            ),
            "eft": _first_of("Eft", "EFT", "col_8", record=bank),
            "swift": _first_of("Swift", "SWIFT", "col_9", record=bank),
        })

    # --- Branches (flat list, each row has bank_name) ---
    for row in raw_data.get("branches", []):
        result["branch_info"].append(_transform_branch_row(row))

    # --- ATMs (flat list, each row has bank_name) ---
    for row in raw_data.get("atms", []):
        result["atm_info"].append(_transform_branch_row(row))

    logger.info(
        "Transformed bank info: %d banks, %d branches, %d ATMs, %d history records",
        len(result["bank_info"]),
        len(result["branch_info"]),
        len(result["atm_info"]),
        len(result["historical_events"]),
    )
    return result
