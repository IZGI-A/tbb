"""Scrapes regional statistics from TBB verisistemi via Selenium.

Navigates to the regional statistics page, selects filters via
DevExtreme dxList checkboxes, triggers report generation, and
extracts the resulting pivot grid data.
"""

import logging
import time
from typing import Any

from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)

REGIONS_PAGE = "index.php?/tbb/report_bolgeler"


class RegionScraper(TBBScraper):

    def _navigate_to_page(self):
        self.navigate(REGIONS_PAGE)
        time.sleep(5)
        self.dismiss_tour()

    def _select_filters(self):
        """Select default filters on the regions page.

        The page has three dxList widgets:
        - ``#bolgelerList``  (regions/cities)
        - ``#yillarList``    (years)
        - ``#parametrelerList`` (parameters/metrics)
        """
        # Select "Tüm Bölgeler" (index 0 = all regions)
        self.select_dx_list_items("bolgelerList", indices=[0])
        time.sleep(1)

        # Select first 3 years (most recent)
        self.select_dx_list_items("yillarList", indices=[0, 1, 2])
        time.sleep(1)

        # Select all parameters
        self.select_dx_list_items("parametrelerList")
        time.sleep(1)

    def scrape_region_data(self) -> tuple[list[dict], list[dict]]:
        """Navigate, select filters, generate report, extract data."""
        self._navigate_to_page()
        self._select_filters()

        # Region page doesn't require TP/YP/TOPLAM flags for validation,
        # but showPivotResults checks bolgeler/yillar/parametreler arrays.

        # Read year info from the selected object
        period_info = self.execute_js("""
            var periods = [];
            if (typeof selected === 'undefined') return periods;
            var yillar = selected.yillar || [];
            for (var i = 0; i < yillar.length; i++) {
                periods.push({year: yillar[i], month: 0, month_str: ''});
            }
            return periods;
        """) or []
        logger.info("Periods: %s", period_info)

        self.generate_report(wait_seconds=30)

        pivot_records = self.extract_pivot_data()
        logger.info("Extracted %d pivot records for regions", len(pivot_records))

        return pivot_records, period_info

    def scrape_all(
        self,
        year_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape: generate report and extract regional data."""
        try:
            pivot_records, period_info = self.scrape_region_data()
        except Exception as e:
            logger.error("Failed to scrape region data: %s", e)
            return []

        if not pivot_records:
            logger.warning("No region data found")
            return []

        all_records: list[dict[str, Any]] = []
        for record in pivot_records:
            rec = dict(record)

            # _col_text is the year (e.g. "2024")
            col_text = rec.pop("_col_text", "")
            year_id, _ = self.parse_turkish_period(col_text)
            rec["_year_id"] = year_id
            rec["_year_text"] = col_text

            # Map pivot row fields to expected keys
            if "SEÇİLMİŞ KALEMLER" in rec:
                rec["_parameter_text"] = rec["SEÇİLMİŞ KALEMLER"]
            if "İL/BÖLGE" in rec:
                rec["Bölge"] = rec["İL/BÖLGE"]

            # Region pivot has a single data field called "TP"
            # Rename to "Toplam" for consistency with transformer
            if "TP" in rec and "Toplam" not in rec:
                rec["Toplam"] = rec.pop("TP")

            all_records.append(rec)

        logger.info("Total regional records scraped: %d", len(all_records))
        return all_records
