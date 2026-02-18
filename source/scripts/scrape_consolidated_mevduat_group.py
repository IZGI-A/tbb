"""Scrape consolidated data for 'Mevduat Bankaları' group (group_id=1).

Usage (inside airflow container):
    python -m scripts.scrape_consolidated_mevduat_group
"""

import logging
import sys

from scrapers.financial_scraper import FinancialScraper, TABLE_TYPES
from etl.transformers import transform_financial
from etl.clickhouse_loader import load_financial_statements

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MEVDUAT_GROUP_ID = 1


def main():
    logger.info("Starting consolidated scrape for Mevduat Bankaları group")

    with FinancialScraper() as scraper:
        scraper._navigate_to_page()
        scraper._select_table_type("consolidated", select_all=True)
        scraper._select_bank_group(MEVDUAT_GROUP_ID)
        scraper.set_distribution_flags(tp=True, yp=True, toplam=True)

        period_info = scraper.get_periods_from_js()
        logger.info("Periods: %s", period_info)

        hierarchy = scraper._extract_hierarchy_lookup()
        api_hierarchy = scraper._fetch_api_hierarchy()

        scraper.generate_report(wait_seconds=45)

        pivot_records = scraper.extract_pivot_data(pivot_selector="#pivotBanka1")
        logger.info("Extracted %d pivot records", len(pivot_records))

        if not pivot_records:
            logger.error("No pivot records extracted. Aborting.")
            sys.exit(1)

        table_label = TABLE_TYPES["consolidated"]["label"]
        enriched = scraper._enrich_records(
            pivot_records, period_info, table_label, hierarchy,
            api_hierarchy=api_hierarchy,
        )

    transformed = transform_financial(enriched)
    logger.info("Transformed %d records", len(transformed))

    count = load_financial_statements(transformed)
    logger.info("Loaded %d rows into ClickHouse", count)

    bank_counts = {}
    for row in transformed:
        bn = row.get("bank_name", "unknown")
        bank_counts[bn] = bank_counts.get(bn, 0) + 1

    logger.info("=== SUMMARY ===")
    for bn, cnt in sorted(bank_counts.items()):
        logger.info("  %s: %d rows", bn, cnt)


if __name__ == "__main__":
    main()
