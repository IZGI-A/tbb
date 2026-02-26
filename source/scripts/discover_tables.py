"""Discover available table types and periods on the TBB financial page.

Usage (inside Airflow container):
  python3 -m scripts.discover_tables
  python3 -m scripts.discover_tables --table-index 2   # show periods for index 2

This helps determine the correct button index for legacy (pre-2018) tables
and lists their available period keys.
"""

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Discover TBB table types and periods")
    parser.add_argument(
        "--table-index", type=int, default=None,
        help="After listing tables, select this index and show its periods",
    )
    args = parser.parse_args()

    from scrapers.financial_scraper import FinancialScraper

    with FinancialScraper() as scraper:
        # 1. Discover all table types
        print("\n=== Available Table Types ===")
        tables = scraper.discover_table_types()
        if not tables:
            print("  (no tables found — check if page loaded correctly)")
        for t in tables:
            print(f"  index={t['index']}  label={t['label']}")

        # 2. If --table-index given, select that table and list periods
        if args.table_index is not None:
            idx = args.table_index
            print(f"\n=== Periods for table index {idx} ===")
            scraper.click_dx_select_all(index=idx)
            import time
            time.sleep(3)
            periods = scraper._get_available_periods()
            if not periods:
                print("  (no periods found)")
            for p in periods:
                print(
                    f"  key={p['key']}  {p['year']}/{p['month']:02d}"
                    f"  ({p.get('month_str', '')})"
                )
            print(f"\n  Total: {len(periods)} periods")


if __name__ == "__main__":
    main()
