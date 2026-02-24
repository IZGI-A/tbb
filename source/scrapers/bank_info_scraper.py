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

    def _get_bank_options(self) -> list[dict[str, str]]:
        """Get available bank options from the bank_select dropdown."""
        try:
            bank_select = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "select[name*='bank'], #bank_select, select[name='bank_select']")
                )
            )
            sel = Select(bank_select)
            return [
                {"value": o.get_attribute("value") or "", "text": o.text.strip()}
                for o in sel.options
                if o.text.strip() != "Hepsi"
            ]
        except (TimeoutException, NoSuchElementException):
            return []

    def _select_bank(self, bank_text: str):
        """Select a specific bank from the bank_select dropdown."""
        try:
            bank_select = self.driver.find_element(
                By.CSS_SELECTOR, "select[name*='bank'], #bank_select, select[name='bank_select']"
            )
            sel = Select(bank_select)
            sel.select_by_visible_text(bank_text)
            time.sleep(1)
        except (NoSuchElementException, Exception) as e:
            logger.warning("Could not select bank '%s': %s", bank_text, e)

    def scrape_branches(self, branch_type: str = "Yurtiçi Şube", bank_name: str | None = None) -> list[dict[str, str]]:
        """Scrape branches or ATMs from the subeler page.

        Args:
            branch_type: "Yurtiçi Şube" for domestic branches, "ATM" for ATMs,
                         or other types like "Yurtdışı Şube", "Temsilcilik", etc.
            bank_name: If provided, filter by this specific bank name.
        """
        logger.info("Navigating to subeler page (type=%s, bank=%s)", branch_type, bank_name or "Hepsi")
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

        # Select specific bank if provided
        if bank_name:
            self._select_bank(bank_name)

        self._click_listele(timeout=60)

        rows = self.parse_table()
        # Clean whitespace in all fields
        for row in rows:
            for key in row:
                if isinstance(row[key], str):
                    row[key] = _clean(row[key])

        logger.info("Scraped %d rows for branch type '%s'", len(rows), branch_type)
        return rows

    def scrape_branches_per_bank(self, branch_type: str = "ATM") -> list[dict[str, str]]:
        """Scrape branches/ATMs bank-by-bank to avoid memory crashes.

        Navigates to the page once to get the bank list, then iterates
        through each bank with a fresh page load per bank.
        """
        logger.info("Navigating to subeler page to get bank list")
        self.driver.get(SUBELER_URL)
        time.sleep(3)
        self._dismiss_cookie_banner()

        bank_options = self._get_bank_options()
        logger.info("Found %d banks for per-bank scrape", len(bank_options))

        all_rows: list[dict[str, str]] = []
        for i, bank in enumerate(bank_options):
            bank_text = bank["text"]
            try:
                self._restart_driver()
                rows = self.scrape_branches(branch_type, bank_name=bank_text)
                all_rows.extend(rows)
                logger.info(
                    "[%d/%d] Bank '%s': %d %s rows (total: %d)",
                    i + 1, len(bank_options), bank_text, len(rows), branch_type, len(all_rows),
                )
            except Exception as e:
                logger.warning(
                    "[%d/%d] Bank '%s' failed: %s — skipping",
                    i + 1, len(bank_options), bank_text, e,
                )
        return all_rows

    def _restart_driver(self):
        """Close and recreate the Chrome driver to free memory."""
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = self._create_driver()

    def scrape_all(self) -> dict[str, Any]:
        """Scrape all bank data: bank list, branches, and ATMs.

        Restarts the browser between each step to prevent tab crashes
        from excessive memory usage.

        Returns dict with keys: banks, branches, atms
        """
        banks = self.scrape_bank_list()

        self._restart_driver()
        branches = self.scrape_branches("Yurtiçi Şube")

        self._restart_driver()
        try:
            atms = self.scrape_branches_per_bank("ATM")
        except Exception as e:
            logger.warning("ATM scrape failed: %s — continuing without ATMs", e)
            atms = []

        logger.info(
            "Scrape complete: %d banks, %d branches, %d ATMs",
            len(banks), len(branches), len(atms),
        )
        return {"banks": banks, "branches": branches, "atms": atms}
