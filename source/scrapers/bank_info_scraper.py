import logging
from typing import Any

from scrapers.base import TBBApiClient

logger = logging.getLogger(__name__)


class BankInfoScraper:
    """Scrapes bank information from TBB API.

    Uses bankalar and bankaGruplari routes.
    """

    def __init__(self, client: TBBApiClient | None = None):
        self.client = client or TBBApiClient()

    def fetch_banks(self) -> list[dict]:
        """Fetch the full bank list."""
        data = self.client.call("bankalar")
        logger.info("Fetched %d banks", len(data) if isinstance(data, list) else 0)
        return data if isinstance(data, list) else []

    def fetch_bank_groups(self) -> list[dict]:
        """Fetch bank group classifications."""
        data = self.client.call("bankaGruplari")
        return data if isinstance(data, list) else []

    def fetch_bank_detail(self, bank_id: int) -> dict[str, Any]:
        """Fetch detailed info for a specific bank (branches, ATMs, history)."""
        data = self.client.call("bankaDetay", {"bankaId": bank_id})
        return data if isinstance(data, dict) else {}

    def scrape_all(self) -> dict[str, Any]:
        """Full scrape pipeline: banks + groups + details.

        Returns:
            Dict with keys: banks, groups, details
        """
        banks = self.fetch_banks()
        groups = self.fetch_bank_groups()

        # Build group lookup
        group_map: dict[int, dict] = {}
        for g in groups:
            gid = g.get("ID")
            if gid is not None:
                group_map[gid] = g

        # Enrich banks with group info
        for bank in banks:
            group_id = bank.get("GRUP_ID")
            if group_id and group_id in group_map:
                bank["_group"] = group_map[group_id]

        # Fetch details for each bank
        details = []
        for bank in banks:
            bank_id = bank.get("ID")
            if bank_id is None:
                continue

            detail = self.fetch_bank_detail(bank_id)
            if detail:
                detail["_bank"] = bank
                details.append(detail)

        logger.info(
            "Scraped %d banks, %d groups, %d details",
            len(banks),
            len(groups),
            len(details),
        )

        return {
            "banks": banks,
            "groups": groups,
            "details": details,
        }
