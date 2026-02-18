"""Scrapes financial statements from TBB verisistemi via Selenium.

Navigates to the financial tables page (DevExtreme UI), selects table type
and bank group via treeview controls, triggers report generation, and
parses the resulting pivot grid.
"""

import logging
import re
import time
from typing import Any

import requests
from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)

# Regex to extract trailing item ID from text like "Balıkçılık (16330)"
_ITEM_ID_RE = re.compile(r"\((\d+)\)\s*$")
# Fallback: handle malformed IDs like "Diğer 103722)" (missing opening paren)
_ITEM_ID_FALLBACK_RE = re.compile(r"\b(\d{4,})\)\s*$")
# Regex to strip arrow prefix like "------>" or "->"
_ARROW_RE = re.compile(r"^-*>\s*")
# Regex to extract leading Arabic number prefix like "1.1.1" or "16.6.2"
_ARABIC_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)*)")
# Arabic → Roman numeral (up to 25 for TBB tables)
_ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
    8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII",
    14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII",
    19: "XIX", 20: "XX", 21: "XXI", 22: "XXII", 23: "XXIII",
    24: "XXIV", 25: "XXV",
}

FINANCIAL_PAGE = "index.php?/tbb/report_mali"

# TBB public API (returns full item hierarchy with UST_UK parent chains)
TBB_API_URL = "https://verisistemi.tbb.org.tr/api/router"

# Known DB section roots — hierarchy paths start from the deepest one
KNOWN_SECTIONS = {
    "1. VARLIKLAR", "2. YÜKÜMLÜLÜKLER", "3. NAZIM HESAPLAR",
    "4. GELİR-GİDER TABLOSU",
    "5. ÖZKAYNAKLARDA MUHASEBELEŞTİRİLEN GELİR GİDER KALEMLERİ",
    "5. KAR VEYA ZARAR VE DİĞER KAPSAMLI GELİR TABLOSU",
    "6. ÖZKAYNAK DEĞİŞİM TABLOSU",
    "6. ÖZKAYNAK DEĞİŞİM TABLOSU-Cari",
    "6. ÖZKAYNAK DEĞİŞİM TABLOSU-Önceki",
    "7. NAKİT AKIŞ TABLOSU",
    "8. KAR DAĞITIM TABLOSU", "9. DİPNOTLAR",
}
KNOWN_DIPNOTS = {
    "1. MALİ BÜNYE İLE İLGİLİ DİPNOTLAR",
    "2. AKTİFLERLE İLGİLİ DİPNOTLAR",
    "3. PASİFLERLE İLGİLİ DİPNOTLAR",
    "4. NAZIM HESAPLARLA İLGİLİ DİPNOTLAR",
    "5. GELİR TABLOSU İLE İLGİLİ DİPNOTLAR",
    "6. RİSK GRUBUNA AİT DİPNOTLAR",
}
_ALL_KNOWN = KNOWN_SECTIONS | KNOWN_DIPNOTS

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

        Returns a dict mapping item ID → {name, parent_id, parent_name,
        root_name, ancestors: [top-down list of ancestor names]}.
        """
        result = self.execute_js("""
            if (typeof mlt_data_maliTablolar === 'undefined') return null;
            var lookup = mlt_data_maliTablolar;
            var keys = Object.keys(lookup);
            var out = {};
            for (var i = 0; i < keys.length; i++) {
                var it = lookup[keys[i]];
                var parentItem = it.UST_UK ? lookup[it.UST_UK] : null;
                // Walk up the full ancestor chain
                var ancestors = [];
                var cur = it.UST_UK;
                var visited = {};
                while (cur && lookup[cur] && !visited[cur]) {
                    visited[cur] = true;
                    ancestors.unshift(lookup[cur].TR_ADI || '');
                    cur = lookup[cur].UST_UK;
                }
                out[it.UNIQUE_KEY] = {
                    name: it.TR_ADI || '',
                    parent_id: it.UST_UK || 0,
                    parent_name: parentItem ? (parentItem.TR_ADI || '') : '',
                    root_name: it.ROOT_TR_ADI || '',
                    ancestors: ancestors
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

        # Fetch TBB API hierarchy once (has correct UST_UK parent chains)
        api_hierarchy = self._fetch_api_hierarchy()

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
                    api_hierarchy=api_hierarchy,
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
                            api_hierarchy=api_hierarchy,
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

            try:
                banks = self._get_available_banks()
            except Exception as e:
                logger.error("Failed to get bank list (tab may have crashed): %s", e)
                continue

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
                            api_hierarchy=api_hierarchy,
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

    @staticmethod
    def _fetch_api_hierarchy() -> dict[int, dict]:
        """Fetch full item hierarchy from TBB public API.

        Returns dict mapping UNIQUE_KEY → {"name": str, "full_path": str}.
        The full_path starts from the deepest known DB section root
        (e.g. "1. MALİ BÜNYE İLE İLGİLİ DİPNOTLAR > subsection > item").

        This is preferred over JS page extraction because the API returns
        correct UST_UK parent chains, while the JS data is often flat.
        """
        try:
            resp = requests.post(
                TBB_API_URL,
                json={"route": "maliTablolarAll"},
                headers={
                    "Content-Type": "application/json",
                    "token": "asd",
                    "role": "1",
                    "LANG": "tr",
                },
                verify=False,
                timeout=120,
            )
            resp.raise_for_status()
            tbb_items = resp.json()
        except Exception as e:
            logger.error("Failed to fetch TBB API hierarchy: %s", e)
            return {}

        logger.info("Fetched %d items from TBB API", len(tbb_items))
        lookup = {
            item["UNIQUE_KEY"]: item
            for item in tbb_items
            if item.get("UNIQUE_KEY")
        }

        def _api_clean(name: str) -> str:
            name = _ITEM_ID_RE.sub("", name)
            name = _ITEM_ID_FALLBACK_RE.sub("", name)
            return name.strip()

        def _build_full_path(item: dict) -> str:
            """Build path from deepest known DB section to item (inclusive)."""
            name = _api_clean(item.get("TR_ADI", ""))
            chain = []
            cur = item.get("UST_UK")
            visited = set()
            while cur and cur in lookup and cur not in visited:
                visited.add(cur)
                parent = lookup[cur]
                chain.append(_api_clean(parent.get("TR_ADI", "")))
                cur = parent.get("UST_UK")
            chain.reverse()
            chain.append(name)
            # Start from deepest known section
            start_idx = 0
            for i, part in enumerate(chain):
                if part in _ALL_KNOWN:
                    start_idx = i
            # Safety: skip accounting system names that leaked into the path
            while start_idx < len(chain) and chain[start_idx].startswith("TFRS"):
                start_idx += 1
            return " > ".join(chain[start_idx:])

        result: dict[int, dict] = {}
        for item in tbb_items:
            uk = item.get("UNIQUE_KEY")
            if not uk:
                continue
            name = _api_clean(item.get("TR_ADI", ""))
            full_path = _build_full_path(item)
            result[uk] = {"name": name, "full_path": full_path}

        logger.info("Built API hierarchy paths for %d items", len(result))
        return result

    @staticmethod
    def _build_hierarchy_path(
        item_name: str,
        root: str,
        known_items: set[str],
    ) -> tuple[str, str]:
        """Infer full hierarchy path from Arabic numbering convention.

        Returns (main_statement_path, child_statement).
        Used as fallback when API hierarchy is unavailable.
        """
        m = _ARABIC_PREFIX_RE.match(item_name)
        if not m:
            return root, item_name

        num_str = m.group(1).rstrip(".")
        parts = num_str.split(".")

        path = [root]

        first_num = int(parts[0])
        roman = _ROMAN.get(first_num)
        if roman:
            prefix_dot = f"{roman}."
            prefix_sp = f"{roman} "
            for ki in known_items:
                if ki.startswith(prefix_dot) or ki.startswith(prefix_sp):
                    path.append(ki)
                    break

        for depth in range(1, len(parts) - 1):
            intermediate_prefix = ".".join(parts[: depth + 1])
            for ki in known_items:
                if ki.startswith(intermediate_prefix + " "):
                    path.append(ki)
                    break
                if ki.startswith(intermediate_prefix + "."):
                    rest = ki[len(intermediate_prefix) + 1:]
                    if rest and not rest[0].isdigit():
                        path.append(ki)
                        break

        return " > ".join(path), item_name

    def _enrich_records(
        self,
        pivot_records: list[dict],
        period_info: list[dict],
        statement_label: str,
        hierarchy: dict[int, dict] | None = None,
        api_hierarchy: dict[int, dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Add period, statement, and hierarchy metadata to pivot records.

        Uses TBB API hierarchy as primary source (correct UST_UK chains).
        Falls back to JS page hierarchy + numbering inference when API
        data is unavailable for an item.
        """
        api_hierarchy = api_hierarchy or {}
        hierarchy = hierarchy or {}

        # Build a lookup: "YYYY M" → period dict
        period_lookup: dict[str, dict] = {}
        for p in period_info:
            key = f"{p['year']} {p['month']}"
            period_lookup[key] = p

        # Pre-compute items_by_root for numbering-based fallback
        items_by_root: dict[str, set[str]] = {}
        if hierarchy:
            for info in hierarchy.values():
                name = self._clean_item_name(info.get("name", ""))
                ancestors = info.get("ancestors", [])
                if ancestors:
                    section_root = self._clean_item_name(ancestors[0])
                    if section_root:
                        items_by_root.setdefault(section_root, set()).add(name)

        enriched: list[dict[str, Any]] = []
        api_hits = 0

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

            item_id = self._extract_item_id(raw_kalem)

            # --- PRIMARY: TBB API hierarchy (correct UST_UK parent chains) ---
            if item_id and item_id in api_hierarchy:
                info = api_hierarchy[item_id]
                full_path = info["full_path"]
                name = info["name"]
                parts = full_path.split(" > ")
                if len(parts) > 1:
                    rec["Ana Kalem"] = " > ".join(parts[:-1])
                    rec["Alt Kalem"] = name
                else:
                    # Item is a root section itself
                    rec["Ana Kalem"] = name
                    rec["Alt Kalem"] = ""
                api_hits += 1

            # --- FALLBACK: JS hierarchy + numbering inference ---
            elif item_id and item_id in hierarchy:
                info = hierarchy[item_id]
                item_name = self._clean_item_name(info.get("name", raw_kalem))
                root_name = info.get("root_name", "").strip()
                parent_name = self._clean_item_name(info.get("parent_name", ""))

                if not parent_name or parent_name == root_name:
                    rec["Ana Kalem"] = item_name
                    rec["Alt Kalem"] = ""
                else:
                    known = items_by_root.get(parent_name, set())
                    if not known:
                        for hi in hierarchy.values():
                            pn = self._clean_item_name(hi.get("parent_name", ""))
                            if pn == parent_name:
                                known.add(self._clean_item_name(hi.get("name", "")))
                        known.discard("")

                    main_path, child = self._build_hierarchy_path(
                        item_name, parent_name, known,
                    )
                    rec["Ana Kalem"] = main_path
                    rec["Alt Kalem"] = child

            # --- LAST RESORT ---
            else:
                rec["Ana Kalem"] = self._clean_item_name(raw_kalem)
                rec["Alt Kalem"] = ""

            enriched.append(rec)

        logger.info(
            "Enriched %d records (%d from API hierarchy, %d fallback)",
            len(enriched), api_hits, len(enriched) - api_hits,
        )
        return enriched
