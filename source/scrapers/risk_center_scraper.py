"""Scrapes risk center data from TBB verisistemi via Selenium.

Navigates to the risk center page, selects a report name and its
categories via DevExtreme dxList / dxTreeView / dxCheckBox widgets,
triggers report generation, and extracts the resulting pivot grid data.
"""

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

    def _select_filters(self, report_index: int = 0):
        """Select default filters on the risk center page.

        Flow:
        1. Click a report name in ``#raporAdiList`` (dxList, single-select)
        2. Wait for ``#kategorilerList`` (dxTreeView) to reload with categories
        3. Select all categories via ``treeView.selectAll()``
        4. Select periods in ``#yillarList`` (dxList)
        5. Enable distribution-value checkboxes (PERSON, COUNT, AMOUNT)
        """
        # 1. Click report name item (triggers kategoriler reload)
        self.execute_js(f"""
            var items = document.querySelectorAll('#raporAdiList .dx-item');
            if (items.length > {report_index}) items[{report_index}].click();
        """)
        time.sleep(3)

        # 2. Select all categories from the treeview
        self.execute_js("$('#kategorilerList').dxTreeView('instance').selectAll();")
        time.sleep(1)

        # 3. Select first 3 periods (most recent, format "YYYY-MM")
        self.select_dx_list_items("yillarList", indices=[0, 1, 2])
        time.sleep(1)

        # 4. Enable value flags via dxCheckBox + JS selected object
        for flag_id in ("fbasPerson", "fbasCount", "fbasAmount"):
            self.set_dx_checkbox(flag_id, True)
        self.execute_js(
            "selected.PERSON = true; selected.COUNT = true; selected.AMOUNT = true;"
        )
        time.sleep(1)

    def scrape_risk_data(self) -> tuple[list[dict], list[dict]]:
        """Navigate, select filters, generate report, extract data."""
        self._navigate_to_page()
        self._select_filters()

        # Read period info from selected.yillar (items are {DONEM: "YYYY-MM"})
        period_info = self.execute_js("""
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
        logger.info("Periods: %s", period_info)

        self.generate_report(wait_seconds=30)

        pivot_records = self.extract_pivot_data()
        logger.info("Extracted %d pivot records for risk center", len(pivot_records))

        return pivot_records, period_info

    def scrape_all(
        self,
        period_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape: generate report and extract risk center data."""
        try:
            pivot_records, period_info = self.scrape_risk_data()
        except Exception as e:
            logger.error("Failed to scrape risk center data: %s", e)
            return []

        if not pivot_records:
            logger.warning("No risk center data found")
            return []

        all_records: list[dict[str, Any]] = []
        for record in pivot_records:
            rec = dict(record)

            # _col_text may contain "Report Name Category" from column tree
            col_text = rec.pop("_col_text", "")

            # Try to match period from the pivot row fields (YIL is a row field)
            if "YIL" in rec:
                year_val = str(rec["YIL"])
                parts = year_val.split("-")
                rec["_year_id"] = int(parts[0]) if parts[0].isdigit() else 0
                rec["_month_id"] = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                rec["_period_text"] = year_val
            else:
                year_id, month_id = self.parse_turkish_period(col_text)
                rec["_year_id"] = year_id
                rec["_month_id"] = month_id
                rec["_period_text"] = col_text

            # Map pivot fields to transformer-compatible keys
            if "RAPOR ADI" in rec:
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

            all_records.append(rec)

        logger.info("Total risk center records scraped: %d", len(all_records))
        return all_records
