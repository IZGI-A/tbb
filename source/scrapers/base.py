import json
import os
import time
import logging
import re

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    JavascriptException,
)

from config import settings

logger = logging.getLogger(__name__)

# Turkish month name → number mapping (with ASCII variants)
TURKISH_MONTHS = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4,
    "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8,
    "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
    "Subat": 2, "Mayis": 5, "Agustos": 8,
    "Eylul": 9, "Kasim": 11, "Aralik": 12,
}


class TBBScraper:
    """Base Selenium scraper for TBB verisistemi.

    Provides headless Chrome driver, page navigation, element waiting,
    rate limiting, HTML table parsing, and DevExtreme component helpers.
    """

    WAIT_TIMEOUT = 30  # seconds to wait for elements

    def __init__(self):
        self.driver = self._create_driver()
        self.base_url = settings.TBB_BASE_URL
        self._last_action_time: float = 0

    def _create_driver(self) -> webdriver.Chrome:
        options = Options()
        if settings.SELENIUM_HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--lang=tr")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        if settings.CHROME_BINARY_PATH:
            options.binary_location = settings.CHROME_BINARY_PATH

        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        if chromedriver_path:
            service = Service(executable_path=chromedriver_path)
        else:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)
        return driver

    # ------------------------------------------------------------------ #
    #  Core navigation & waiting
    # ------------------------------------------------------------------ #

    def _rate_limit(self):
        elapsed = time.time() - self._last_action_time
        wait = settings.TBB_RATE_LIMIT_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_action_time = time.time()

    def navigate(self, path: str):
        """Navigate to a page under TBB base URL."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger.info("Navigating to: %s", url)
        self._rate_limit()
        self.driver.get(url)

    def wait_for_element(self, by: str, value: str, timeout: int | None = None) -> object:
        timeout = timeout or self.WAIT_TIMEOUT
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_for_clickable(self, by: str, value: str, timeout: int | None = None) -> object:
        timeout = timeout or self.WAIT_TIMEOUT
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def wait_for_table(self, timeout: int | None = None):
        timeout = timeout or self.WAIT_TIMEOUT
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
        except TimeoutException:
            logger.warning("Table did not load within %d seconds", timeout)

    # ------------------------------------------------------------------ #
    #  Legacy helpers (kept for backwards compatibility)
    # ------------------------------------------------------------------ #

    def select_dropdown(self, element_id: str, value: str):
        self._rate_limit()
        try:
            el = self.driver.find_element(By.ID, element_id)
            select = Select(el)
            select.select_by_visible_text(value)
        except NoSuchElementException:
            logger.warning("Dropdown '%s' not found", element_id)

    def select_dropdown_by_value(self, element_id: str, value: str):
        self._rate_limit()
        try:
            el = self.driver.find_element(By.ID, element_id)
            select = Select(el)
            select.select_by_value(value)
        except NoSuchElementException:
            logger.warning("Dropdown '%s' not found", element_id)

    def get_dropdown_options(self, element_id: str) -> list[dict[str, str]]:
        try:
            el = self.driver.find_element(By.ID, element_id)
            select = Select(el)
            return [
                {"value": opt.get_attribute("value") or "", "text": opt.text.strip()}
                for opt in select.options
                if opt.get_attribute("value")
            ]
        except NoSuchElementException:
            logger.warning("Dropdown '%s' not found", element_id)
            return []

    def click_button(self, by: str, value: str):
        self._rate_limit()
        btn = self.wait_for_clickable(by, value)
        btn.click()

    # ------------------------------------------------------------------ #
    #  HTML parsing
    # ------------------------------------------------------------------ #

    def get_page_source(self) -> BeautifulSoup:
        return BeautifulSoup(self.driver.page_source, "lxml")

    def parse_table(self, soup: BeautifulSoup | None = None) -> list[dict[str, str]]:
        if soup is None:
            soup = self.get_page_source()

        table = soup.find("table")
        if not table or not isinstance(table, Tag):
            logger.warning("No table found on page")
            return []

        headers: list[str] = []
        thead = table.find("thead")
        if thead and isinstance(thead, Tag):
            for th in thead.find_all("th"):
                headers.append(th.get_text(strip=True))

        rows: list[dict[str, str]] = []
        tbody = table.find("tbody")
        if tbody and isinstance(tbody, Tag):
            for tr in tbody.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if headers and len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                elif cells:
                    rows.append({f"col_{i}": c for i, c in enumerate(cells)})

        logger.info("Parsed table: %d headers, %d rows", len(headers), len(rows))
        return rows

    def parse_all_tables(self, soup: BeautifulSoup | None = None) -> list[list[dict[str, str]]]:
        if soup is None:
            soup = self.get_page_source()

        tables = soup.find_all("table")
        results = []
        for table in tables:
            if not isinstance(table, Tag):
                continue
            temp_soup = BeautifulSoup(str(table), "lxml")
            rows = self.parse_table(temp_soup)
            if rows:
                results.append(rows)
        return results

    @staticmethod
    def clean_number(text: str) -> str:
        """Clean Turkish-format numbers: 1.234.567,89 → 1234567.89"""
        if not text or text == "-" or text == "":
            return ""
        text = text.strip()
        text = text.replace(".", "").replace(",", ".")
        text = re.sub(r"[^\d.\-]", "", text)
        return text

    # ------------------------------------------------------------------ #
    #  DevExtreme helpers (new TBB site)
    # ------------------------------------------------------------------ #

    def dismiss_tour(self, timeout: int = 5):
        """Dismiss the tour/wizard popup by clicking 'Bitir' button."""
        try:
            btns = WebDriverWait(self.driver, timeout).until(
                lambda d: d.find_elements(
                    By.XPATH, "//button[contains(text(),'Bitir')]"
                )
            )
            if btns:
                btns[0].click()
                time.sleep(1)
                logger.info("Tour dismissed")
        except TimeoutException:
            logger.debug("No tour popup found")

    def click_dx_select_all(self, index: int = 0):
        """Click a '.btn-dx-select.all' button by index.

        These buttons select a treeview item together with all its children.
        """
        self._rate_limit()
        buttons = self.driver.find_elements(By.CSS_SELECTOR, ".btn-dx-select.all")
        if index < len(buttons):
            buttons[index].click()
            time.sleep(1)
            logger.info("Clicked btn-dx-select.all[%d]", index)
        else:
            logger.warning(
                "btn-dx-select.all[%d] not found (%d available)", index, len(buttons)
            )

    def click_dx_select_only(self, index: int = 0):
        """Click a '.btn-dx-select.only' button by index.

        These buttons select only the specific treeview item (no children).
        """
        self._rate_limit()
        buttons = self.driver.find_elements(By.CSS_SELECTOR, ".btn-dx-select.only")
        if index < len(buttons):
            buttons[index].click()
            time.sleep(1)
            logger.info("Clicked btn-dx-select.only[%d]", index)
        else:
            logger.warning(
                "btn-dx-select.only[%d] not found (%d available)", index, len(buttons)
            )

    def execute_js(self, script: str, *args):
        """Execute JavaScript on the page with error handling."""
        try:
            return self.driver.execute_script(script, *args)
        except JavascriptException as e:
            logger.warning("JS execution failed: %s", e)
            return None

    # ------------------------------------------------------------------ #
    #  dxList / dxCheckBox helpers
    # ------------------------------------------------------------------ #

    def select_dx_list_items(self, list_id: str, indices: list[int] | None = None):
        """Select items in a DevExtreme dxList widget by indices.

        If *indices* is ``None``, selects **all** items.
        """
        if indices is None:
            self.execute_js(f"""
                var w = $('#{list_id}').dxList('instance');
                var items = w.option('items');
                for (var i = 0; i < items.length; i++) {{ w.selectItem(i); }}
            """)
            logger.info("Selected ALL items in dxList #%s", list_id)
        else:
            for idx in indices:
                self.execute_js(f"$('#{list_id}').dxList('instance').selectItem({idx});")
            logger.info("Selected %d items in dxList #%s", len(indices), list_id)
        time.sleep(1)

    def set_dx_checkbox(self, checkbox_id: str, value: bool = True):
        """Set a DevExtreme dxCheckBox widget value."""
        self.execute_js(
            f"$('#{checkbox_id}').dxCheckBox('instance').option('value', {str(value).lower()});"
        )

    # ------------------------------------------------------------------ #
    #  Distribution flags
    # ------------------------------------------------------------------ #

    def set_distribution_flags(self, tp: bool = True, yp: bool = True, toplam: bool = True):
        """Set TP / YP / TOPLAM distribution flags on the page's ``selected`` JS object.

        These must be ``true`` before generating a report, otherwise the
        ``showPivotResults`` validation will reject the request.
        """
        self.execute_js(
            f"selected.TP = {str(tp).lower()}; "
            f"selected.YP = {str(yp).lower()}; "
            f"selected.TOPLAM = {str(toplam).lower()};"
        )
        logger.info("Distribution flags set: TP=%s YP=%s TOPLAM=%s", tp, yp, toplam)

    def generate_report(self, wait_seconds: int = 15):
        """Call ``showResults('pivot')`` via JS and wait for the pivot grid to render."""
        self._rate_limit()
        self.execute_js("showResults('pivot')")
        logger.info("Called showResults('pivot'), waiting %ds for report...", wait_seconds)

        # Poll for pivot data to appear
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(3)
            has_data = self.execute_js(
                "return document.querySelectorAll('.dx-pivotgrid').length > 0 "
                "&& document.querySelectorAll('table tr').length > 5"
            )
            if has_data:
                logger.info("Report rendered")
                return
        logger.warning("Report did not render within %ds", wait_seconds)

    def click_report_button(self, wait_seconds: int = 20):
        """Click 'Rapor Al' button and wait for the report to render."""
        self._rate_limit()
        try:
            btn = self.driver.find_element(
                By.XPATH, "//button[contains(text(),'Rapor Al')]"
            )
            btn.click()
            logger.info("Clicked 'Rapor Al', waiting %ds for report...", wait_seconds)
            time.sleep(wait_seconds)
        except NoSuchElementException:
            logger.warning("'Rapor Al' button not found")

    def get_periods_from_js(self) -> list[dict]:
        """Extract period info from the site's JS data model.

        Returns list of dicts with keys: year, month, month_str, key.
        """
        result = self.execute_js("""
            var periods = [];
            if (typeof selected === 'undefined' || !selected.donemlerIds) return periods;
            var dataSource = (typeof mlt_data_donemler !== 'undefined') ? mlt_data_donemler
                           : (typeof data_donemler !== 'undefined') ? data_donemler
                           : null;
            for (var i = 0; i < selected.donemlerIds.length; i++) {
                var id = selected.donemlerIds[i];
                var d = dataSource ? dataSource[id] : null;
                if (d) {
                    periods.push({year: d.YIL, month: d.AY, month_str: d.AY_STR || '', key: id});
                } else {
                    periods.push({year: 0, month: 0, month_str: '', key: id});
                }
            }
            return periods;
        """)
        return result or []

    def get_basket_periods(self) -> list[str]:
        """Extract selected period texts from the filter basket."""
        periods = self.get_periods_from_js()
        if periods:
            return [
                f"{p['year']} {p['month_str']}" if p['month_str']
                else f"{p['year']}/{p['month']}"
                for p in periods
            ]
        return []

    @staticmethod
    def parse_turkish_period(text: str) -> tuple[int, int]:
        """Parse period text into (year, month).

        Handles formats like '2025 Eylul', '2024/12', '12/2024'.
        """
        text = text.strip()
        # Try "YYYY MonthName" or "MonthName YYYY" format
        for month_name, month_num in TURKISH_MONTHS.items():
            if month_name.lower() in text.lower():
                year_match = re.findall(r"\d{4}", text)
                if year_match:
                    return int(year_match[0]), month_num
        # Try numeric formats
        numbers = re.findall(r"\d+", text)
        if len(numbers) >= 2:
            a, b = int(numbers[0]), int(numbers[1])
            if a > 100:
                return a, b
            elif b > 100:
                return b, a
        if len(numbers) == 1:
            return int(numbers[0]), 0
        return 0, 0

    def extract_pivot_data(self, pivot_selector: str = "") -> list[dict]:
        """Extract data from DevExtreme pivot grid on the page.

        Tries the DevExtreme JS API first; falls back to HTML table parsing.
        Returns a list of flat dicts with row field names, ``_col_text``,
        and data field values (e.g. TP, YP, Toplam).
        """
        records = self._extract_pivot_js(pivot_selector)
        if records:
            return records
        logger.info("JS pivot extraction unavailable, falling back to HTML parsing")
        return self._extract_pivot_html()

    def _extract_pivot_js(self, pivot_selector: str = "") -> list[dict] | None:
        """Extract pivot grid data via the DevExtreme JS widget API.

        Traverses the row/column trees down to leaf nodes, then builds one
        flat record per (leaf-row, leaf-column) combination.  Row fields
        are named after their captions (e.g. ``MUHASEBE SİSTEMİ``).
        """
        script = """
        var sel = arguments[0];
        var pg = null;
        if (sel) {
            try { pg = $(sel).dxPivotGrid('instance'); } catch(e) {}
        }
        if (!pg) {
            var els = document.querySelectorAll('.dx-pivotgrid');
            for (var i = 0; i < els.length; i++) {
                try { pg = $(els[i]).dxPivotGrid('instance'); break; } catch(e) {}
            }
        }
        if (!pg) return null;

        var ds  = pg.getDataSource();
        var data = ds.getData();
        var fields = ds.fields();

        var rowFieldNames = [];
        var colFieldNames = [];
        var dataFieldNames = [];
        for (var f = 0; f < fields.length; f++) {
            if (fields[f].area === 'row')
                rowFieldNames.push(fields[f].caption || fields[f].dataField || 'row_'+rowFieldNames.length);
            else if (fields[f].area === 'column')
                colFieldNames.push(fields[f].caption || fields[f].dataField || 'col_'+colFieldNames.length);
            else if (fields[f].area === 'data')
                dataFieldNames.push(fields[f].caption || fields[f].dataField || 'value_'+dataFieldNames.length);
        }

        /* Collect leaf items with their full path texts */
        function leaves(items, path) {
            var out = [];
            if (!items) return out;
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                var p  = path.concat([it.text || '']);
                if (it.children && it.children.length)
                    out = out.concat(leaves(it.children, p));
                else
                    out.push({ix: it.index, path: p});
            }
            return out;
        }

        var leafRows = leaves(data.rows, []);
        var leafCols = leaves(data.columns, []);

        var records = [];
        for (var r = 0; r < leafRows.length; r++) {
            var row = leafRows[r];
            for (var c = 0; c < leafCols.length; c++) {
                var col = leafCols[c];
                var cv;
                try { cv = data.values[row.ix][col.ix]; } catch(e) { continue; }
                if (!cv) continue;

                var rec = {};
                for (var k = 0; k < row.path.length; k++)
                    rec[k < rowFieldNames.length ? rowFieldNames[k] : 'row_'+k] = row.path[k];
                rec._col_text = col.path.join(' ');
                for (var k = 0; k < col.path.length; k++)
                    rec[k < colFieldNames.length ? colFieldNames[k] : 'col_'+k] = col.path[k];

                for (var d = 0; d < dataFieldNames.length; d++) {
                    if (d < cv.length && cv[d] != null)
                        rec[dataFieldNames[d]] = cv[d];
                }
                records.push(rec);
            }
        }
        return records.length ? JSON.stringify(records) : null;
        """
        try:
            result = self.execute_js(script, pivot_selector)
            if result:
                if isinstance(result, str):
                    return json.loads(result)
                if isinstance(result, list):
                    return result
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse pivot JS result: %s", e)
        return None

    def _extract_pivot_html(self) -> list[dict]:
        """Parse pivot grid data from HTML tables (fallback)."""
        soup = self.get_page_source()

        # Try to find tables inside dx-pivotgrid containers
        pivot_els = soup.find_all(
            lambda tag: tag.name == "div"
            and tag.get("class")
            and any("dx-pivotgrid" in c for c in tag["class"])
        )

        all_records: list[dict] = []

        for pivot_el in pivot_els:
            tables = pivot_el.find_all("table")
            if not tables:
                continue

            # Heuristic: pick tables with actual data content
            for table in tables:
                if not isinstance(table, Tag):
                    continue
                trs = table.find_all("tr")
                if len(trs) < 2:
                    continue
                for tr in trs:
                    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if any(cells):
                        all_records.append(
                            {f"col_{i}": c for i, c in enumerate(cells)}
                        )

        # Ultimate fallback: parse all visible tables on the page
        if not all_records:
            logger.info("No pivot HTML found, falling back to all tables")
            all_records = self.parse_table(soup)

        return all_records

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def close(self):
        if self.driver:
            self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
