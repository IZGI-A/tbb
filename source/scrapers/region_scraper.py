import logging
from typing import Any

from source.scrapers.base import TBBApiClient

logger = logging.getLogger(__name__)


class RegionScraper:
    """Scrapes regional statistics from TBB API.

    Chain: blgYillarAll → blgParametrelerAll → blgBolgelerAll → blgDegerler
    """

    def __init__(self, client: TBBApiClient | None = None):
        self.client = client or TBBApiClient()

    def fetch_years(self) -> list[dict]:
        """Fetch available years for regional statistics."""
        data = self.client.call("blgYillarAll")
        logger.info("Fetched %d years", len(data) if isinstance(data, list) else 0)
        return data if isinstance(data, list) else []

    def fetch_parameters(self) -> list[dict]:
        """Fetch available parameters/metrics."""
        data = self.client.call("blgParametrelerAll")
        return data if isinstance(data, list) else []

    def fetch_regions(self) -> list[dict]:
        """Fetch available regions."""
        data = self.client.call("blgBolgelerAll")
        return data if isinstance(data, list) else []

    def fetch_values(
        self,
        year_id: int,
        parameter_id: int,
        region_ids: list[int],
    ) -> list[dict]:
        """Fetch regional values for a year/parameter/region combination."""
        data = self.client.call(
            "blgDegerler",
            {
                "yilId": year_id,
                "parametreId": parameter_id,
                "bolgeIds": region_ids,
            },
        )
        return data if isinstance(data, list) else []

    def scrape_all(
        self,
        year_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Full scrape pipeline: years → parameters → regions → values.

        Args:
            year_ids: Specific year IDs to scrape. If None, scrapes all.

        Returns:
            List of raw value records from the API.
        """
        all_values = []

        years = self.fetch_years()
        if year_ids:
            years = [y for y in years if y.get("ID") in year_ids]

        parameters = self.fetch_parameters()
        regions = self.fetch_regions()
        region_ids = [r["ID"] for r in regions if "ID" in r]

        if not region_ids:
            logger.warning("No regions found")
            return []

        for year in years:
            yid = year["ID"]
            logger.info("Processing year: %s (ID=%d)", year.get("YIL", "?"), yid)

            for param in parameters:
                param_id = param.get("ID")
                if param_id is None:
                    continue

                values = self.fetch_values(yid, param_id, region_ids)
                for v in values:
                    v["_year"] = year
                    v["_parameter"] = param
                all_values.extend(values)

            logger.info("Year %d: total %d records so far", yid, len(all_values))

        logger.info("Total regional records scraped: %d", len(all_values))
        return all_values
