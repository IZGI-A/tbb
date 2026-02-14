"""Batch INSERT into ClickHouse tables."""

import logging
from typing import Any

from db.clickhouse import get_clickhouse_client

logger = logging.getLogger(__name__)

BATCH_SIZE = 10_000


def _chunked(data: list, size: int):
    for i in range(0, len(data), size):
        yield data[i : i + size]


def load_financial_statements(rows: list[dict[str, Any]]) -> int:
    """Insert financial statement rows into ClickHouse."""
    if not rows:
        return 0

    client = get_clickhouse_client()
    total = 0

    columns = [
        "accounting_system", "main_statement", "child_statement",
        "bank_name", "year_id", "month_id",
        "amount_tc", "amount_fc", "amount_total", "crawl_timestamp",
    ]

    for batch in _chunked(rows, BATCH_SIZE):
        data = [
            [row.get(col) for col in columns]
            for row in batch
        ]
        client.execute(
            f"INSERT INTO tbb.financial_statements ({', '.join(columns)}) VALUES",
            data,
        )
        total += len(batch)
        logger.info("Inserted batch of %d financial rows (total: %d)", len(batch), total)

    client.disconnect()
    logger.info("Loaded %d financial statement rows", total)
    return total


def load_region_statistics(rows: list[dict[str, Any]]) -> int:
    """Insert regional statistics rows into ClickHouse."""
    if not rows:
        return 0

    client = get_clickhouse_client()
    total = 0

    columns = ["region", "metric", "year_id", "value", "crawl_timestamp"]

    for batch in _chunked(rows, BATCH_SIZE):
        data = [
            [row.get(col) for col in columns]
            for row in batch
        ]
        client.execute(
            f"INSERT INTO tbb.region_statistics ({', '.join(columns)}) VALUES",
            data,
        )
        total += len(batch)
        logger.info("Inserted batch of %d region rows (total: %d)", len(batch), total)

    client.disconnect()
    logger.info("Loaded %d region statistics rows", total)
    return total


def load_risk_center(rows: list[dict[str, Any]]) -> int:
    """Insert risk center rows into ClickHouse."""
    if not rows:
        return 0

    client = get_clickhouse_client()
    total = 0

    columns = [
        "report_name", "category", "person_count",
        "quantity", "amount", "year_id", "month_id", "crawl_timestamp",
    ]

    for batch in _chunked(rows, BATCH_SIZE):
        data = [
            [row.get(col) for col in columns]
            for row in batch
        ]
        client.execute(
            f"INSERT INTO tbb.risk_center ({', '.join(columns)}) VALUES",
            data,
        )
        total += len(batch)
        logger.info("Inserted batch of %d risk center rows (total: %d)", len(batch), total)

    client.disconnect()
    logger.info("Loaded %d risk center rows", total)
    return total
