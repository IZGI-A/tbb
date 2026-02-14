"""UPSERT into PostgreSQL tables."""

import logging
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)


def _get_connection():
    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    )


def load_bank_info(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    conn = _get_connection()
    cur = conn.cursor()

    sql = """
        INSERT INTO bank_info (
            bank_group, sub_bank_group, bank_name, address,
            board_president, general_manager, phone_fax,
            web_kep_address, eft, swift
        ) VALUES %s
        ON CONFLICT (bank_name) DO UPDATE SET
            bank_group = EXCLUDED.bank_group,
            sub_bank_group = EXCLUDED.sub_bank_group,
            address = EXCLUDED.address,
            board_president = EXCLUDED.board_president,
            general_manager = EXCLUDED.general_manager,
            phone_fax = EXCLUDED.phone_fax,
            web_kep_address = EXCLUDED.web_kep_address,
            eft = EXCLUDED.eft,
            swift = EXCLUDED.swift,
            updated_at = CURRENT_TIMESTAMP
    """

    values = [
        (
            r["bank_group"], r["sub_bank_group"], r["bank_name"],
            r["address"], r["board_president"], r["general_manager"],
            r["phone_fax"], r["web_kep_address"], r["eft"], r["swift"],
        )
        for r in rows
    ]

    execute_values(cur, sql, values)
    conn.commit()
    count = len(values)
    cur.close()
    conn.close()

    logger.info("Upserted %d bank_info rows", count)
    return count


def load_branch_info(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    conn = _get_connection()
    cur = conn.cursor()

    sql = """
        INSERT INTO branch_info (
            bank_name, branch_name, address, district,
            city, phone, fax, opening_date
        ) VALUES %s
        ON CONFLICT (bank_name, branch_name) DO UPDATE SET
            address = EXCLUDED.address,
            district = EXCLUDED.district,
            city = EXCLUDED.city,
            phone = EXCLUDED.phone,
            fax = EXCLUDED.fax,
            opening_date = EXCLUDED.opening_date,
            updated_at = CURRENT_TIMESTAMP
    """

    values = [
        (
            r["bank_name"], r["branch_name"], r["address"],
            r["district"], r["city"], r["phone"],
            r["fax"], r.get("opening_date"),
        )
        for r in rows
    ]

    execute_values(cur, sql, values)
    conn.commit()
    count = len(values)
    cur.close()
    conn.close()

    logger.info("Upserted %d branch_info rows", count)
    return count


def load_atm_info(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    conn = _get_connection()
    cur = conn.cursor()

    sql = """
        INSERT INTO atm_info (
            bank_name, branch_name, address, district,
            city, phone, fax, opening_date
        ) VALUES %s
        ON CONFLICT (bank_name, branch_name, address) DO UPDATE SET
            district = EXCLUDED.district,
            city = EXCLUDED.city,
            phone = EXCLUDED.phone,
            fax = EXCLUDED.fax,
            opening_date = EXCLUDED.opening_date,
            updated_at = CURRENT_TIMESTAMP
    """

    # Deduplicate by PK (bank_name, branch_name, address) — keep last occurrence
    seen: dict[tuple, tuple] = {}
    for r in rows:
        key = (r["bank_name"], r["branch_name"], r["address"])
        seen[key] = (
            r["bank_name"], r["branch_name"], r["address"],
            r["district"], r["city"], r["phone"],
            r["fax"], r.get("opening_date"),
        )
    values = list(seen.values())

    execute_values(cur, sql, values)
    conn.commit()
    count = len(values)
    cur.close()
    conn.close()

    logger.info("Upserted %d atm_info rows", count)
    return count


def load_historical_events(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    conn = _get_connection()
    cur = conn.cursor()

    sql = """
        INSERT INTO historical_events (
            bank_name, founding_date, historical_event
        ) VALUES %s
        ON CONFLICT (bank_name) DO UPDATE SET
            founding_date = EXCLUDED.founding_date,
            historical_event = EXCLUDED.historical_event,
            updated_at = CURRENT_TIMESTAMP
    """

    values = [
        (r["bank_name"], r.get("founding_date"), r.get("historical_event", ""))
        for r in rows
    ]

    execute_values(cur, sql, values)
    conn.commit()
    count = len(values)
    cur.close()
    conn.close()

    logger.info("Upserted %d historical_events rows", count)
    return count


def load_all_bank_data(transformed: dict[str, list[dict]]) -> dict[str, int]:
    """Load all bank data in correct FK order."""
    counts = {}
    counts["bank_info"] = load_bank_info(transformed["bank_info"])
    counts["branch_info"] = load_branch_info(transformed["branch_info"])
    counts["atm_info"] = load_atm_info(transformed["atm_info"])
    counts["historical_events"] = load_historical_events(transformed["historical_events"])
    logger.info("All bank data loaded: %s", counts)
    return counts
