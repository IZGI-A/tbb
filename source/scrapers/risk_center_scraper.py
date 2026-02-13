import logging
from typing import Any

from source.scrapers.base import TBBApiClient

logger = logging.getLogger(__name__)


class RiskCenterScraper:
    """Scrapes risk center data from TBB API.

    Chain: kkbYillarAll → kkbRaporAdiAll → kkbKategorilerAll → kkbDegerler
    """

    def __init__(self, client: TBBApiClient | None = None):
        self.client = client or TBBApiClient()

    def fetch_periods(self) -> list[dict]:
        """Fetch available years/periods for risk center data."""
        data = self.client.call("kkbYillarAll")
        logger.info("Fetched %d periods", len(data) if isinstance(data, list) else 0)
        return data if isinstance(data, list) else []

    def fetch_reports(self) -> list[dict]:
        """Fetch available report types."""
        data = self.client.call("kkbRaporAdiAll")
        return data if isinstance(data, list) else []

    def fetch_categories(self, report_id: int) -> list[dict]:
        """Fetch categories for a specific report."""
        data = self.client.call("kkbKategorilerAll", {"raporId": report_id})
        return data if isinstance(data, list) else []

    def fetch_values(
        self,
        period_id: int,
        report_id: int,
        category_ids: list[int],
    ) -> list[dict]:
        """Fetch risk center values for a period/report/category combination."""
        data = self.client.call(
            "kkbDegerler",
            {
                "donemId": period_id,
                "raporId": report_id,
                "kategoriIds": category_ids,
            },
        )
        return data if isinstance(data, list) else []

    def scrape_all(
        self,
        period_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape pipeline: periods → reports → categories → values.

        Args:
            period_ids: Specific period IDs to scrape. If None, scrapes all.

        Returns:
            List of raw value records from the API.
        """
        all_values = []

        periods = self.fetch_periods()
        if period_ids:
            periods = [p for p in periods if p.get("ID") in period_ids]

        reports = self.fetch_reports()

        for report in reports:
            report_id = report.get("ID")
            if report_id is None:
                continue

            categories = self.fetch_categories(report_id)
            category_ids = [c["ID"] for c in categories if "ID" in c]

            if not category_ids:
                logger.warning("No categories for report %s", report.get("ADI", "?"))
                continue

            for period in periods:
                pid = period["ID"]
                values = self.fetch_values(pid, report_id, category_ids)
                for v in values:
                    v["_period"] = period
                    v["_report"] = report
                all_values.extend(values)

            logger.info(
                "Report '%s': total %d records so far",
                report.get("ADI", "?"),
                len(all_values),
            )

        logger.info("Total risk center records scraped: %d", len(all_values))
        return all_values
