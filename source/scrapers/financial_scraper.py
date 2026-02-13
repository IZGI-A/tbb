import logging
from typing import Any

from source.scrapers.base import TBBApiClient

logger = logging.getLogger(__name__)


class FinancialScraper:
    """Scrapes financial statements from TBB API.

    Chain: donemler → maliTablolarAll → bankalar → degerler
    """

    def __init__(self, client: TBBApiClient | None = None):
        self.client = client or TBBApiClient()

    def fetch_periods(self) -> list[dict]:
        """Fetch available periods (year/month combinations)."""
        data = self.client.call("donemler")
        logger.info("Fetched %d periods", len(data) if isinstance(data, list) else 0)
        return data if isinstance(data, list) else []

    def fetch_statements(self, period_id: int) -> list[dict]:
        """Fetch all financial statement types for a period."""
        data = self.client.call("maliTablolarAll", {"donemId": period_id})
        return data if isinstance(data, list) else []

    def fetch_banks(self, period_id: int) -> list[dict]:
        """Fetch banks available for a period."""
        data = self.client.call("bankalar", {"donemId": period_id})
        return data if isinstance(data, list) else []

    def fetch_values(
        self,
        period_id: int,
        statement_id: int,
        bank_ids: list[int],
    ) -> list[dict]:
        """Fetch actual financial values for a statement/period/bank combination."""
        data = self.client.call(
            "degerler",
            {
                "donemId": period_id,
                "maliTabloId": statement_id,
                "bankaIds": bank_ids,
            },
        )
        return data if isinstance(data, list) else []

    def scrape_all(
        self,
        period_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape pipeline: periods → statements → banks → values.

        Args:
            period_ids: Specific period IDs to scrape. If None, scrapes all.

        Returns:
            List of raw value records from the API.
        """
        all_values = []

        periods = self.fetch_periods()
        if period_ids:
            periods = [p for p in periods if p.get("ID") in period_ids]

        for period in periods:
            pid = period["ID"]
            logger.info(
                "Processing period: %s/%s (ID=%d)",
                period.get("YIL", "?"),
                period.get("AY", "?"),
                pid,
            )

            statements = self.fetch_statements(pid)
            banks = self.fetch_banks(pid)
            bank_ids = [b["ID"] for b in banks if "ID" in b]

            if not bank_ids:
                logger.warning("No banks found for period %d", pid)
                continue

            for stmt in statements:
                stmt_id = stmt.get("ID")
                if stmt_id is None:
                    continue

                values = self.fetch_values(pid, stmt_id, bank_ids)
                # Enrich each value with period metadata
                for v in values:
                    v["_period"] = period
                    v["_statement"] = stmt
                all_values.extend(values)

            logger.info(
                "Period %d: collected %d value records",
                pid,
                len(all_values),
            )

        logger.info("Total financial records scraped: %d", len(all_values))
        return all_values
