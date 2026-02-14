"""Scrapes financial statements from TBB verisistemi via Selenium.

Navigates to the financial tables page (DevExtreme UI), selects table type
and bank group via treeview controls, triggers report generation, and
parses the resulting pivot grid.
"""

import logging
import time
from typing import Any

from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)

FINANCIAL_PAGE = "index.php?/tbb/report_mali"

# The .btn-dx-select buttons appear in DOM order:
# index 0 → SOLO, index 1 → CONSOLIDATED
TABLE_TYPES = {
    "solo": {"index": 0, "label": "TFRS9-SOLO"},
    "consolidated": {"index": 1, "label": "TFRS9-KONSOLIDE"},
}

BANK_GROUP_ALL = 5  # Turkiye Bankacilik Sistemi


class FinancialScraper(TBBScraper):

    def _navigate_to_page(self):
        self.navigate(FINANCIAL_PAGE)
        time.sleep(5)
        self.dismiss_tour()

    def _select_table_type(self, table_key: str = "solo", select_all: bool = True):
        """Select a financial table type from the treeview."""
        info = TABLE_TYPES.get(table_key, TABLE_TYPES["solo"])
        if select_all:
            self.click_dx_select_all(index=info["index"])
        else:
            self.click_dx_select_only(index=info["index"])
        time.sleep(2)
        logger.info("Selected table type: %s (select_all=%s)", table_key, select_all)

    def _select_bank_group(self, group_id: int = BANK_GROUP_ALL):
        """Select a bank group via JS."""
        self.execute_js(f"bankaGruplari_select(0, {group_id})")
        time.sleep(2)
        logger.info("Selected bank group id=%d", group_id)

    def scrape_financial_data(
        self,
        table_key: str = "solo",
        bank_group_id: int = BANK_GROUP_ALL,
    ) -> tuple[list[dict[str, Any]], list[dict]]:
        """Navigate, configure filters, generate report, and extract data.

        Returns (pivot_records, period_info).
        """
        self._navigate_to_page()

        self._select_table_type(table_key, select_all=True)
        self._select_bank_group(bank_group_id)

        # Distribution flags must be set before generating the report
        self.set_distribution_flags(tp=True, yp=True, toplam=True)

        # Read period metadata from the JS data model
        period_info = self.get_periods_from_js()
        logger.info("Periods: %s", period_info)

        # Generate the pivot report via JS
        self.generate_report(wait_seconds=30)

        # Extract pivot data
        pivot_records = self.extract_pivot_data(pivot_selector="#pivotBanka1")
        logger.info(
            "Extracted %d pivot records for table=%s", len(pivot_records), table_key,
        )

        return pivot_records, period_info

    def scrape_all(
        self,
        table_keys: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape: generate reports for each table type and extract data.

        Args:
            table_keys: Table types to scrape ('solo', 'consolidated').
                        If None, scrapes only 'solo'.

        Returns:
            list[dict] with keys compatible with transform_financial.
        """
        if table_keys is None:
            table_keys = ["solo"]

        all_records: list[dict[str, Any]] = []

        for table_key in table_keys:
            table_label = TABLE_TYPES.get(table_key, {}).get("label", table_key)

            try:
                pivot_records, period_info = self.scrape_financial_data(
                    table_key=table_key,
                )
            except Exception as e:
                logger.error("Failed to scrape table '%s': %s", table_key, e)
                continue

            if not pivot_records:
                logger.warning("No data for table '%s'", table_key)
                continue

            records = self._enrich_records(pivot_records, period_info, table_label)
            all_records.extend(records)
            logger.info(
                "Table '%s': %d records (total: %d)",
                table_key, len(records), len(all_records),
            )

        logger.info("Total financial records scraped: %d", len(all_records))
        return all_records

    def _enrich_records(
        self,
        pivot_records: list[dict],
        period_info: list[dict],
        statement_label: str,
    ) -> list[dict[str, Any]]:
        """Add period and statement metadata to pivot records."""
        # Build a lookup: "YYYY M" → period dict
        period_lookup: dict[str, dict] = {}
        for p in period_info:
            key = f"{p['year']} {p['month']}"
            period_lookup[key] = p

        enriched: list[dict[str, Any]] = []
        for record in pivot_records:
            rec = dict(record)

            # Parse period from _col_text (e.g. "2025 9")
            col_text = rec.pop("_col_text", "")
            pinfo = period_lookup.get(col_text)
            if pinfo:
                rec["_year_id"] = pinfo["year"]
                rec["_month_id"] = pinfo["month"]
                rec["_period_text"] = f"{pinfo['year']} {pinfo.get('month_str', pinfo['month'])}"
            else:
                year_id, month_id = self.parse_turkish_period(col_text)
                rec["_year_id"] = year_id
                rec["_month_id"] = month_id
                rec["_period_text"] = col_text

            rec["_statement_text"] = statement_label

            # Map pivot row fields to transformer-compatible keys
            # Row fields from pivot: MUHASEBE SİSTEMİ, SEÇİLMİŞ KALEMLER, BANKA / BANKA GRUP
            if "SEÇİLMİŞ KALEMLER" in rec:
                rec["Ana Kalem"] = rec.pop("SEÇİLMİŞ KALEMLER")
            if "BANKA / BANKA GRUP" in rec:
                rec["Banka"] = rec.pop("BANKA / BANKA GRUP")
            if "MUHASEBE SİSTEMİ" in rec:
                rec["Muhasebe Sistemi"] = rec.pop("MUHASEBE SİSTEMİ")

            enriched.append(rec)

        return enriched
