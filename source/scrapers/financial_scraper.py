"""Scrapes financial statements from TBB verisistemi via Selenium.

Navigates to the financial tables page (DevExtreme UI), selects table type
and bank group via treeview controls, triggers report generation, and
parses the resulting pivot grid.
"""

import logging
import re
import time
from typing import Any

from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)

# Regex to extract trailing item ID from text like "Balıkçılık (16330)"
_ITEM_ID_RE = re.compile(r"\((\d+)\)\s*$")
# Fallback: handle malformed IDs like "Diğer 103722)" (missing opening paren)
_ITEM_ID_FALLBACK_RE = re.compile(r"\b(\d{4,})\)\s*$")
# Regex to strip arrow prefix like "------>" or "->"
_ARROW_RE = re.compile(r"^-*>\s*")

FINANCIAL_PAGE = "index.php?/tbb/report_mali"

# The .btn-dx-select buttons appear in DOM order:
# index 0 → SOLO, index 1 → CONSOLIDATED
TABLE_TYPES = {
    "solo": {"index": 0, "label": "TFRS9-SOLO"},
    "consolidated": {"index": 1, "label": "TFRS9-KONSOLIDE"},
}

BANK_GROUP_ALL = 5  # Turkiye Bankacilik Sistemi
BANK_BATCH_SIZE = 5  # Banks per batch to avoid tab crash

# Bank group IDs to scrape (each generates a separate report with group name as bank_name)
BANK_GROUP_IDS = [1, 2, 3, 4, 9, 13]


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

    def _get_available_banks(self) -> list[dict]:
        """Get list of individual banks from the bankalarList dxList.

        Returns list of {code, name} dicts.
        """
        result = self.execute_js("""
            var list = $('#bankalarList').dxList('instance');
            var items = list.option('items');
            if (!items) return '[]';
            var out = [];
            for (var i = 0; i < items.length; i++) {
                out.push({code: items[i].BANKA_KODU, name: items[i].TR_ADI, idx: i});
            }
            return JSON.stringify(out);
        """)
        if not result:
            return []
        try:
            return __import__("json").loads(result) if isinstance(result, str) else result
        except Exception:
            return []

    def _select_individual_banks(self, bank_indices: list[int]):
        """Clear all selections and select specific banks by dxList index."""
        # Clear previous selections
        self.execute_js("""
            clearBankaGruplari();
            var list = $('#bankalarList').dxList('instance');
            list.unselectAll();
        """)
        time.sleep(1)

        # Select the specified banks
        for idx in bank_indices:
            self.execute_js(f"$('#bankalarList').dxList('instance').selectItem({idx});")
        time.sleep(1)
        logger.info("Selected %d individual banks", len(bank_indices))

    def _extract_hierarchy_lookup(self) -> dict[int, dict]:
        """Extract the item hierarchy from mlt_data_maliTablolar on the page.

        Returns a dict mapping item ID → {name, parent_id, parent_name, root_name}.
        """
        result = self.execute_js("""
            if (typeof mlt_data_maliTablolar === 'undefined') return null;
            var lookup = mlt_data_maliTablolar;
            var keys = Object.keys(lookup);
            var out = {};
            for (var i = 0; i < keys.length; i++) {
                var it = lookup[keys[i]];
                var parentItem = it.UST_UK ? lookup[it.UST_UK] : null;
                out[it.UNIQUE_KEY] = {
                    name: it.TR_ADI || '',
                    parent_id: it.UST_UK || 0,
                    parent_name: parentItem ? (parentItem.TR_ADI || '') : '',
                    root_name: it.ROOT_TR_ADI || ''
                };
            }
            return JSON.stringify(out);
        """)
        if not result:
            logger.warning("Could not extract hierarchy lookup")
            return {}
        try:
            raw = result if isinstance(result, dict) else __import__("json").loads(result)
            return {int(k): v for k, v in raw.items()}
        except Exception as e:
            logger.warning("Failed to parse hierarchy lookup: %s", e)
            return {}

    def scrape_financial_data(
        self,
        table_key: str = "solo",
        bank_group_id: int = BANK_GROUP_ALL,
    ) -> tuple[list[dict[str, Any]], list[dict], dict[int, dict]]:
        """Navigate, configure filters, generate report, and extract data.

        Returns (pivot_records, period_info, hierarchy_lookup).
        """
        self._navigate_to_page()

        self._select_table_type(table_key, select_all=True)
        self._select_bank_group(bank_group_id)

        # Distribution flags must be set before generating the report
        self.set_distribution_flags(tp=True, yp=True, toplam=True)

        # Read period metadata from the JS data model
        period_info = self.get_periods_from_js()
        logger.info("Periods: %s", period_info)

        # Extract hierarchy before generating report (data is already loaded)
        hierarchy = self._extract_hierarchy_lookup()
        logger.info("Hierarchy lookup: %d items", len(hierarchy))

        # Generate the pivot report via JS
        self.generate_report(wait_seconds=30)

        # Extract pivot data
        pivot_records = self.extract_pivot_data(pivot_selector="#pivotBanka1")
        logger.info(
            "Extracted %d pivot records for table=%s", len(pivot_records), table_key,
        )

        return pivot_records, period_info, hierarchy

    def scrape_all(
        self,
        table_keys: list[str] | None = None,
        include_individual_banks: bool = True,
    ) -> list[dict[str, Any]]:
        """Full scrape: generate reports for each table type and extract data.

        Args:
            table_keys: Table types to scrape ('solo', 'consolidated').
                        If None, scrapes only 'solo'.
            include_individual_banks: If True, also scrape per-bank data
                        in addition to the aggregate.

        Returns:
            list[dict] with keys compatible with transform_financial.
        """
        if table_keys is None:
            table_keys = ["solo"]

        all_records: list[dict[str, Any]] = []

        for table_key in table_keys:
            table_label = TABLE_TYPES.get(table_key, {}).get("label", table_key)

            # --- Phase 1: Aggregate (Türkiye Bankacılık Sistemi) ---
            try:
                pivot_records, period_info, hierarchy = (
                    self.scrape_financial_data(table_key=table_key)
                )
            except Exception as e:
                logger.error("Failed to scrape table '%s': %s", table_key, e)
                continue

            if pivot_records:
                records = self._enrich_records(
                    pivot_records, period_info, table_label, hierarchy,
                )
                all_records.extend(records)
                logger.info(
                    "Table '%s' aggregate: %d records", table_key, len(records),
                )
            else:
                logger.warning("No aggregate data for table '%s'", table_key)

            # --- Phase 2: Bank groups (each group as a separate bank_name) ---
            logger.info("Scraping %d bank groups", len(BANK_GROUP_IDS))
            for group_id in BANK_GROUP_IDS:
                try:
                    self._select_bank_group(group_id)
                    self.set_distribution_flags(tp=True, yp=True, toplam=True)
                    self.generate_report(wait_seconds=30)

                    group_records = self.extract_pivot_data(
                        pivot_selector="#pivotBanka1",
                    )
                    if group_records:
                        enriched = self._enrich_records(
                            group_records, period_info, table_label, hierarchy,
                        )
                        all_records.extend(enriched)
                        logger.info(
                            "Bank group %d: %d records (total: %d)",
                            group_id, len(enriched), len(all_records),
                        )
                    else:
                        logger.warning("No data for bank group %d", group_id)
                except Exception as e:
                    logger.error("Failed bank group %d: %s", group_id, e)

            # --- Phase 3: Individual banks (in batches) ---
            if not include_individual_banks:
                continue

            banks = self._get_available_banks()
            if not banks:
                logger.warning("No individual banks found, skipping per-bank scrape")
                continue

            logger.info(
                "Scraping %d individual banks in batches of %d",
                len(banks), BANK_BATCH_SIZE,
            )

            for batch_start in range(0, len(banks), BANK_BATCH_SIZE):
                batch = banks[batch_start : batch_start + BANK_BATCH_SIZE]
                batch_indices = [b["idx"] for b in batch]
                batch_names = [b["name"] for b in batch]
                batch_num = batch_start // BANK_BATCH_SIZE + 1
                total_batches = (len(banks) + BANK_BATCH_SIZE - 1) // BANK_BATCH_SIZE

                logger.info(
                    "Bank batch %d/%d: %s",
                    batch_num, total_batches, batch_names,
                )

                try:
                    self._select_individual_banks(batch_indices)
                    self.set_distribution_flags(tp=True, yp=True, toplam=True)
                    self.generate_report(wait_seconds=45)

                    batch_records = self.extract_pivot_data(
                        pivot_selector="#pivotBanka1",
                    )
                    if batch_records:
                        enriched = self._enrich_records(
                            batch_records, period_info, table_label, hierarchy,
                        )
                        all_records.extend(enriched)
                        logger.info(
                            "Bank batch %d/%d: %d records (total: %d)",
                            batch_num, total_batches, len(enriched), len(all_records),
                        )
                    else:
                        logger.warning("No data for bank batch %d", batch_num)
                except Exception as e:
                    logger.error(
                        "Failed bank batch %d (%s): %s",
                        batch_num, batch_names, e,
                    )

        logger.info("Total financial records scraped: %d", len(all_records))
        return all_records

    @staticmethod
    def _clean_item_name(text: str) -> str:
        """Remove arrow prefix and trailing ID from an item name.

        '------> Balıkçılık (16330)' → 'Balıkçılık'
        '-> I. FİNANSAL VARLIKLAR (Net) (9996)' → 'I. FİNANSAL VARLIKLAR (Net)'
        'Diğer 103722)' → 'Diğer'
        """
        # Strip arrow prefix
        text = _ARROW_RE.sub("", text)
        # Strip trailing numeric ID in parens, but keep non-numeric parens like "(Net)"
        text = _ITEM_ID_RE.sub("", text)
        # Handle malformed IDs without opening paren (e.g. "Diğer 103722)")
        text = _ITEM_ID_FALLBACK_RE.sub("", text)
        return text.strip()

    @staticmethod
    def _extract_item_id(text: str) -> int | None:
        """Extract the numeric ID from trailing parentheses.

        '------> Balıkçılık (16330)' → 16330
        'Diğer 103722)' → 103722
        """
        m = _ITEM_ID_RE.search(text)
        if m:
            return int(m.group(1))
        # Fallback for malformed IDs
        m = _ITEM_ID_FALLBACK_RE.search(text)
        return int(m.group(1)) if m else None

    def _enrich_records(
        self,
        pivot_records: list[dict],
        period_info: list[dict],
        statement_label: str,
        hierarchy: dict[int, dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Add period, statement, and hierarchy metadata to pivot records."""
        hierarchy = hierarchy or {}

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
            raw_kalem = rec.pop("SEÇİLMİŞ KALEMLER", "")
            if "BANKA / BANKA GRUP" in rec:
                rec["Banka"] = rec.pop("BANKA / BANKA GRUP")
            if "MUHASEBE SİSTEMİ" in rec:
                rec["Muhasebe Sistemi"] = rec.pop("MUHASEBE SİSTEMİ")

            # Split into Ana Kalem (parent) and Alt Kalem (self) using hierarchy
            item_id = self._extract_item_id(raw_kalem)

            if item_id and item_id in hierarchy:
                info = hierarchy[item_id]
                # Use hierarchy's own name (TR_ADI) for cleaner formatting
                item_name = self._clean_item_name(info.get("name", raw_kalem))
                parent_name = self._clean_item_name(info.get("parent_name", ""))
                root_name = info.get("root_name", "").strip()

                # If parent is ROOT (parent_name matches root table name or
                # parent has no further parent), this is a top-level item
                if not parent_name or parent_name == root_name:
                    rec["Ana Kalem"] = item_name
                    rec["Alt Kalem"] = ""
                else:
                    rec["Ana Kalem"] = parent_name
                    rec["Alt Kalem"] = item_name
            else:
                # Fallback: no hierarchy data, put everything in Ana Kalem
                rec["Ana Kalem"] = self._clean_item_name(raw_kalem)
                rec["Alt Kalem"] = ""

            enriched.append(rec)

        return enriched
