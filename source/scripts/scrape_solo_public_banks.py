"""Targeted solo scrape for public capital deposit banks (Kamusal Sermayeli Mevduat Bankaları).

Scrapes TFRS9-SOLO financial data for:
  - T.C. Ziraat Bankası (BANKA_KODU=3)
  - Türkiye Halk Bankası (BANKA_KODU=5)
  - Türkiye Vakıflar Bankası (BANKA_KODU=6)

Uses direct JS manipulation of selected.bankalarIds to bypass
the dxList pageSize limitation (20 items per page).

Usage (inside airflow container):
    python -m scripts.scrape_solo_public_banks
"""

import logging
import sys
import time

from scrapers.financial_scraper import FinancialScraper, TABLE_TYPES
from etl.transformers import transform_financial
from etl.clickhouse_loader import load_financial_statements

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Bank codes from mlt_data_bankalar
TARGET_BANK_CODES = [3, 5, 6]  # Ziraat, Halk, Vakıf


def main():
    logger.info("Starting solo scrape for public capital deposit banks")
    logger.info("Target bank codes: %s", TARGET_BANK_CODES)

    with FinancialScraper() as scraper:
        # 1. Navigate to the financial page
        scraper._navigate_to_page()

        # 2. Select SOLO table type (index 0)
        scraper._select_table_type("solo", select_all=True)

        # 3. Clear bank group selection and set individual bank codes directly
        scraper.execute_js("""
            clearBankaGruplari();
            selected.bankalarIds = arguments[0];
        """, TARGET_BANK_CODES)
        time.sleep(2)
        logger.info("Set selected.bankalarIds = %s", TARGET_BANK_CODES)

        # Verify
        verify = scraper.execute_js("return JSON.stringify(selected.bankalarIds);")
        logger.info("Verified bankalarIds: %s", verify)

        # 4. Set distribution flags
        scraper.set_distribution_flags(tp=True, yp=True, toplam=True)

        # 5. Get period and hierarchy info
        period_info = scraper.get_periods_from_js()
        logger.info("Periods: %s", period_info)

        hierarchy = scraper._extract_hierarchy_lookup()
        api_hierarchy = scraper._fetch_api_hierarchy()

        # 6. Generate report and extract pivot data
        scraper.generate_report(wait_seconds=60)

        pivot_records = scraper.extract_pivot_data(pivot_selector="#pivotBanka1")
        logger.info("Extracted %d pivot records", len(pivot_records))

        if not pivot_records:
            logger.error("No pivot records extracted. Aborting.")
            sys.exit(1)

        # Log sample record
        logger.info("Sample record keys: %s", list(pivot_records[0].keys()))
        logger.info("Sample record: %s", pivot_records[0])

        # Check unique bank names in the data
        bank_names = set()
        for r in pivot_records:
            bn = r.get("BANKA / BANKA GRUP", "")
            if bn:
                bank_names.add(bn)
        logger.info("Unique banks in pivot data: %s", bank_names)

        # 7. Enrich records
        table_label = TABLE_TYPES["solo"]["label"]
        enriched = scraper._enrich_records(
            pivot_records, period_info, table_label, hierarchy,
            api_hierarchy=api_hierarchy,
        )
        logger.info("Enriched %d records", len(enriched))

    # 8. Transform
    transformed = transform_financial(enriched)
    logger.info("Transformed %d records", len(transformed))

    # 9. Load into ClickHouse
    count = load_financial_statements(transformed)
    logger.info("Loaded %d rows into ClickHouse", count)

    # Summary
    bank_counts = {}
    for row in transformed:
        bn = row.get("bank_name", "unknown")
        bank_counts[bn] = bank_counts.get(bn, 0) + 1

    logger.info("=== SUMMARY ===")
    for bn, cnt in sorted(bank_counts.items()):
        logger.info("  %s: %d rows", bn, cnt)
    logger.info("Total: %d rows loaded", count)


if __name__ == "__main__":
    main()
