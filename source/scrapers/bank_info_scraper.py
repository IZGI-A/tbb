"""Scrapes bank info, branches, and ATMs from tbb.org.tr.

Data sources:
- Bank list: https://www.tbb.org.tr/banka-ve-sektor-bilgileri/banka-bilgileri/bankalarimiz
- Branches/ATMs: https://www.tbb.org.tr/banka-ve-sektor-bilgileri/banka-bilgileri/subeler

Both pages use Drupal AJAX forms. "Listele" triggers a POST that fills
#table-wrapper with an HTML table.
"""

import logging
import re
import time
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from scrapers.base import TBBScraper

logger = logging.getLogger(__name__)

TBB_ORG = "https://www.tbb.org.tr"
BANKALARIMIZ_URL = f"{TBB_ORG}/banka-ve-sektor-bilgileri/banka-bilgileri/bankalarimiz"
SUBELER_URL = f"{TBB_ORG}/banka-ve-sektor-bilgileri/banka-bilgileri/subeler"

# Known bank group names (rows with only col_0 that indicate a group change)
_BANK_GROUPS = {
    "Mevduat Bankaları",
    "Kalkınma ve Yatırım Bankaları",
    "Katılım Bankaları",
}


def _clean(text: str) -> str:
    """Collapse whitespace/tabs/newlines into a single space and strip."""
    return re.sub(r"\s+", " ", text).strip()


class BankInfoScraper(TBBScraper):

    def _dismiss_cookie_banner(self, timeout: int = 5):
        """Close the cookie consent banner if present."""
        try:
            btn = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".eu-cookie-compliance-default-button, .agree-button, #popup-buttons .agree-button")
                )
            )
            btn.click()
            time.sleep(1)
            logger.info("Cookie banner dismissed")
        except TimeoutException:
            logger.debug("No cookie banner found")

    def _click_listele(self, timeout: int = 30):
        """Click the 'Listele' submit button and wait for the table to load."""
        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//input[@value='Listele'] | //button[contains(text(),'Listele')]")
                )
            )
            btn.click()
            logger.info("Clicked 'Listele'")
        except TimeoutException:
            logger.warning("'Listele' button not found")
            return

        # Wait for table rows to appear inside #table-wrapper
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#table-wrapper table tbody tr, .view-content table tbody tr")
                )
            )
            time.sleep(2)
            logger.info("Table loaded")
        except TimeoutException:
            logger.warning("Table did not load within %ds", timeout)

    @staticmethod
    def _process_bank_rows(raw_rows: list[dict]) -> list[dict]:
        """Process raw bank table rows: assign groups and clean whitespace.

        The bankalarimiz table mixes group header rows (single col_0) with
        actual bank data rows. Header rows update the current group context.
        """
        banks: list[dict] = []
        current_group = ""
        current_sub_group = ""

        for row in raw_rows:
            # Header row (only col_0) — update group tracking
            if "col_0" in row and len(row) == 1:
                label = _clean(row["col_0"])
                if label in _BANK_GROUPS:
                    current_group = label
                    current_sub_group = ""
                elif label == "Türkiye Bankacılık Sistemi":
                    continue  # top-level header, skip
                else:
                    current_sub_group = label
                continue

            # Actual bank data row — clean all values and add group info
            if "Banka Adı" not in row:
                continue

            bank = {
                "bank_group": current_group,
                "sub_bank_group": current_sub_group,
            }
            for key, value in row.items():
                bank[key] = _clean(str(value)) if value else ""
            banks.append(bank)

        return banks

    def scrape_bank_list(self) -> list[dict[str, str]]:
        """Scrape the bank list from the bankalarimiz page."""
        logger.info("Navigating to bankalarimiz page")
        self.driver.get(BANKALARIMIZ_URL)
        time.sleep(3)

        self._dismiss_cookie_banner()
        self._click_listele()

        raw_rows = self.parse_table()
        banks = self._process_bank_rows(raw_rows)
        logger.info("Scraped %d banks from bankalarimiz", len(banks))
        return banks

    def scrape_branches(self, branch_type: str = "Yurtiçi Şube") -> list[dict[str, str]]:
        """Scrape branches or ATMs from the subeler page.

        Args:
            branch_type: "Yurtiçi Şube" for domestic branches, "ATM" for ATMs,
                         or other types like "Yurtdışı Şube", "Temsilcilik", etc.
        """
        logger.info("Navigating to subeler page (type=%s)", branch_type)
        self.driver.get(SUBELER_URL)
        time.sleep(3)

        self._dismiss_cookie_banner()

        # Select branch type from the dropdown
        try:
            type_select = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "select[name*='sube_tipi'], select[name*='type'], #edit-sube-tipi")
                )
            )
            sel = Select(type_select)
            sel.select_by_visible_text(branch_type)
            logger.info("Selected branch type: %s", branch_type)
            time.sleep(2)
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning("Could not select branch type '%s': %s", branch_type, e)

        self._click_listele(timeout=60)

        rows = self.parse_table()
        # Clean whitespace in all fields
        for row in rows:
            for key in row:
                if isinstance(row[key], str):
                    row[key] = _clean(row[key])

        logger.info("Scraped %d rows for branch type '%s'", len(rows), branch_type)
        return rows

    def scrape_all(self) -> dict[str, Any]:
        """Scrape all bank data: bank list, branches, and ATMs.

        Returns dict with keys: banks, branches, atms
        """
        banks = self.scrape_bank_list()
        branches = self.scrape_branches("Yurtiçi Şube")
        atms = self.scrape_branches("ATM")

        logger.info(
            "Scrape complete: %d banks, %d branches, %d ATMs",
            len(banks), len(branches), len(atms),
        )
        return {"banks": banks, "branches": branches, "atms": atms}
