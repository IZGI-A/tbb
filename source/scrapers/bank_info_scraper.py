"""Bank information scraper — DISABLED.

The TBB verisistemi no longer has a dedicated bank information page
(the old #/banka-bilgileri route has been removed).  This scraper is
kept as a stub so that existing imports do not break.  All methods
return empty results and log a warning.
"""

import logging
from typing import Any

from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)


class BankInfoScraper(TBBScraper):

    _PAGE_REMOVED_MSG = (
        "Bank info page no longer exists on TBB verisistemi. "
        "This scraper is disabled."
    )

    def scrape_bank_list(self) -> list[dict[str, str]]:
        logger.warning(self._PAGE_REMOVED_MSG)
        return []

    def scrape_bank_detail(self, bank_link_index: int) -> dict[str, Any]:
        logger.warning(self._PAGE_REMOVED_MSG)
        return {"info": {}, "branches": [], "atms": [], "history": {}}

    def scrape_all(self) -> dict[str, Any]:
        logger.warning(self._PAGE_REMOVED_MSG)
        return {"banks": [], "details": []}
