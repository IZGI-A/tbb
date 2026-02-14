"""Scrapes risk center data from TBB verisistemi via Selenium.

Navigates to the risk center page, iterates through all available report
names, selects categories via DevExtreme dxList / dxTreeView / dxCheckBox
widgets, triggers report generation, and extracts the resulting pivot data.
"""

import json
import logging
import time
from typing import Any

from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)

RISK_CENTER_PAGE = "index.php?/tbb/report_rm"


class RiskCenterScraper(TBBScraper):

    def _navigate_to_page(self):
        self.navigate(RISK_CENTER_PAGE)
        time.sleep(5)
        self.dismiss_tour()

    def _get_report_names(self) -> list[dict]:
        """Get all report names from ``#raporAdiList``.

        Returns list of ``{idx, text}`` dicts.
        """
        result = self.execute_js("""
            var items = document.querySelectorAll('#raporAdiList .dx-item');
            var out = [];
            for (var i = 0; i < items.length; i++) {
                out.push({idx: i, text: items[i].textContent.trim()});
            }
            return JSON.stringify(out);
        """)
        if not result:
            return []
        try:
            return json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            return []

    def _select_report(self, report_index: int) -> int:
        """Click a report in ``#raporAdiList`` and wait for categories to load.

        Clears ``selected.kategoriler`` and ``selected.raporAdi`` first to
        prevent accumulation from previous reports.

        Returns the number of categories available after loading.
        """
        # Clear accumulated selections from previous report
        self.execute_js(
            "selected.kategoriler = []; selected.raporAdi = [];"
        )

        self.execute_js(
            f"$('#raporAdiList').dxList('instance').selectItem({report_index});"
        )
        time.sleep(3)

        # Count available categories
        cat_count = self.execute_js("""
            try {
                var tv = $('#kategorilerList').dxTreeView('instance');
                var nodes = tv.getNodes();
                function count(arr) {
                    var c = 0;
                    for (var i = 0; i < arr.length; i++) {
                        c++;
                        if (arr[i].children && arr[i].children.length)
                            c += count(arr[i].children);
                    }
                    return c;
                }
                return count(nodes);
            } catch(e) { return 0; }
        """) or 0
        return cat_count

    def _select_filters(self, report_index: int = 0):
        """Select filters for a specific report.

        Assumes the report has already been clicked via ``_select_report()``.
        Selects all categories, first 3 periods, and enables value flags.
        """
        # Select all categories from the treeview
        self.execute_js("$('#kategorilerList').dxTreeView('instance').selectAll();")
        time.sleep(1)

        # Select first 3 periods (most recent, format "YYYY-MM")
        self.select_dx_list_items("yillarList", indices=[0, 1, 2])
        time.sleep(1)

        # Enable value flags via dxCheckBox + JS selected object
        for flag_id in ("fbasPerson", "fbasCount", "fbasAmount"):
            self.set_dx_checkbox(flag_id, True)
        self.execute_js(
            "selected.PERSON = true; selected.COUNT = true; selected.AMOUNT = true;"
        )
        time.sleep(1)

    def _get_period_info(self) -> list[dict]:
        """Read period info from ``selected.yillar``."""
        return self.execute_js("""
            var periods = [];
            if (typeof selected === 'undefined') return periods;
            var yillar = selected.yillar || [];
            for (var i = 0; i < yillar.length; i++) {
                var donem = (typeof yillar[i] === 'object') ? yillar[i].DONEM : String(yillar[i]);
                var parts = donem.split('-');
                var year = parts.length >= 1 ? parseInt(parts[0]) : 0;
                var month = parts.length >= 2 ? parseInt(parts[1]) : 0;
                periods.push({year: year, month: month, month_str: '', key: donem});
            }
            return periods;
        """) or []

    def _enrich_records(
        self,
        pivot_records: list[dict],
        report_name: str,
    ) -> list[dict[str, Any]]:
        """Add period metadata and map pivot field names to transformer keys."""
        enriched: list[dict[str, Any]] = []
        for record in pivot_records:
            rec = dict(record)

            col_text = rec.pop("_col_text", "")

            # Parse period from pivot row field "YIL" (e.g. "2024-09")
            if "YIL" in rec:
                year_val = str(rec["YIL"])
                parts = year_val.split("-")
                rec["_year_id"] = int(parts[0]) if parts[0].isdigit() else 0
                rec["_month_id"] = (
                    int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                )
                rec["_period_text"] = year_val
            else:
                year_id, month_id = self.parse_turkish_period(col_text)
                rec["_year_id"] = year_id
                rec["_month_id"] = month_id
                rec["_period_text"] = col_text

            # Use explicit report name from the iteration
            rec["_report_text"] = report_name

            # Also keep any pivot "RAPOR ADI" field if present
            if "RAPOR ADI" in rec and not rec["_report_text"]:
                rec["_report_text"] = rec["RAPOR ADI"]

            if "KATEGORİ" in rec:
                rec["Kategori"] = rec["KATEGORİ"]

            # Map data fields
            if "KİŞİ SAYISI" in rec:
                rec["Tekil Kişi Sayısı"] = rec.pop("KİŞİ SAYISI")
            if "ADET" in rec:
                rec["Adet"] = rec.pop("ADET")
            if "TUTAR: (Bir TL)" in rec:
                rec["Tutar"] = rec.pop("TUTAR: (Bir TL)")

            enriched.append(rec)
        return enriched

    def scrape_all(
        self,
        period_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape: iterate through all reports and extract data.

        For each report:
        1. Click the report in ``#raporAdiList``
        2. Wait for categories to reload
        3. Skip reports with no meaningful categories
        4. Select all categories, periods, and value flags
        5. Generate report and extract pivot data
        """
        self._navigate_to_page()

        reports = self._get_report_names()
        if not reports:
            logger.error("No reports found on risk center page")
            return []

        logger.info("Found %d reports on risk center page", len(reports))

        all_records: list[dict[str, Any]] = []

        for report in reports:
            idx = report["idx"]
            name = report["text"]
            logger.info(
                "--- Report %d/%d: %s ---", idx + 1, len(reports), name,
            )

            try:
                cat_count = self._select_report(idx)
                if cat_count <= 1:
                    # Reports with only "-" or empty categories (e.g. index 12, 18, 19)
                    logger.info("Skipping report '%s' (only %d categories)", name, cat_count)
                    continue

                logger.info("Report '%s' has %d categories", name, cat_count)

                self._select_filters(report_index=idx)

                self.generate_report(wait_seconds=30)

                pivot_records = self.extract_pivot_data()
                logger.info(
                    "Extracted %d pivot records for '%s'", len(pivot_records), name,
                )

                if pivot_records:
                    enriched = self._enrich_records(pivot_records, name)
                    all_records.extend(enriched)
                    logger.info(
                        "Report '%s': %d records (total: %d)",
                        name, len(enriched), len(all_records),
                    )
                else:
                    logger.warning("No data for report '%s'", name)

            except Exception as e:
                logger.error("Failed report '%s': %s", name, e)

        logger.info("Total risk center records scraped: %d", len(all_records))
        return all_records
