"""Browser-based client for dynamic web scraping.

This module provides BrowserClient using Selenium WebDriver.

IMPORTANT: Selenium is an optional dependency in this repo. Importing the text
scraper framework should not require Selenium unless `client: browser` is used.
"""

# pyright: reportGeneralTypeIssues=false
# pyright: reportMissingImports=false
# pyright: reportRedeclaration=false

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, cast

from .models import ScrapingResult

logger = logging.getLogger(__name__)


class _BrowserClientUnavailable:
    """Placeholder BrowserClient when Selenium is not installed."""

    def __init__(
        self,
        driver_path: Optional[str] = None,
        download_path: Optional[str] = None,
        headless: bool = True,
        timeout: float = 20.0,
        page_load_timeout: float = 30.0,
        implicit_wait: float = 10.0,
    ):
        raise ImportError(
            "Selenium is required for BrowserClient. Install 'selenium' to use client='browser'."
        )


BrowserClient = _BrowserClientUnavailable


try:  # pragma: no cover
    from selenium import webdriver
    from selenium.webdriver import ChromeService, ChromeOptions
    from selenium.webdriver.support.wait import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException

    class _BrowserClientSelenium:
        """Browser-based client for dynamic scraping using Selenium WebDriver."""

        def __init__(
            self,
            driver_path: Optional[str] = None,
            download_path: Optional[str] = None,
            headless: bool = True,
            timeout: float = 20.0,
            page_load_timeout: float = 30.0,
            implicit_wait: float = 10.0,
        ):
            self.driver_path = driver_path
            self.download_path = download_path
            self.headless = headless
            self.timeout = timeout
            self.page_load_timeout = page_load_timeout
            self.implicit_wait = implicit_wait

            self.driver: Any = None
            self.failed_urls: List[tuple] = []

        def start_driver(self) -> None:
            """Initialize and start the Chrome WebDriver."""
            try:
                if self.driver_path:
                    service = ChromeService(executable_path=self.driver_path)
                else:
                    service = ChromeService()

                options = ChromeOptions()
                if self.headless:
                    options.add_argument("--headless")

                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-web-security")
                options.add_argument("--disable-features=VizDisplayCompositor")

                options.add_experimental_option(
                    "excludeSwitches", ["enable-automation"]
                )
                options.add_experimental_option("useAutomationExtension", False)
                options.add_argument("--disable-blink-features=AutomationControlled")

                if self.download_path:
                    prefs = {
                        "download.default_directory": self.download_path,
                        "download.prompt_for_download": False,
                        "download.directory_upgrade": True,
                        "safebrowsing.enabled": True,
                    }
                    options.add_experimental_option("prefs", prefs)

                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.set_page_load_timeout(self.page_load_timeout)
                self.driver.implicitly_wait(self.implicit_wait)

                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                logger.info("Chrome WebDriver started successfully")
            except Exception as exc:
                logger.error(f"Failed to start Chrome WebDriver: {exc}")
                raise

        def close_driver(self) -> None:
            """Close the WebDriver and clean up resources."""
            if self.driver:
                try:
                    self.driver.quit()
                finally:
                    self.driver = None

        def navigate_to_url(self, url: str, retries: int = 3) -> bool:
            """Navigate to a URL with retry logic."""
            if not self.driver:
                raise RuntimeError("WebDriver not started. Call start_driver() first.")

            for attempt in range(retries + 1):
                try:
                    self.driver.get(url)
                    WebDriverWait(self.driver, self.timeout).until(
                        lambda driver: (
                            driver.execute_script("return document.readyState")
                            == "complete"
                        )
                    )
                    return True
                except TimeoutException:
                    logger.warning(f"Timeout loading {url} (attempt {attempt + 1})")
                except WebDriverException as exc:
                    logger.warning(
                        f"WebDriver error for {url}: {exc} (attempt {attempt + 1})"
                    )
                except Exception as exc:
                    logger.error(f"Unexpected error navigating to {url}: {exc}")
                    break

                if attempt < retries:
                    wait_time = 2**attempt
                    time.sleep(wait_time)

            return False

        def find_elements(
            self, selector: str, by: str = "xpath", timeout: Optional[float] = None
        ) -> List[Any]:
            """Find elements using the specified selector."""
            if not self.driver:
                raise RuntimeError("WebDriver not started. Call start_driver() first.")

            timeout = timeout or self.timeout
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return list(self.driver.find_elements(by, selector))

        def extract_element_data(self, element: Any, data_type: str) -> Optional[str]:
            """Extract data from a WebElement."""
            try:
                if data_type == "text":
                    return str(element.text).strip()
                if data_type in {"href", "src", "alt", "title"}:
                    value = element.get_attribute(data_type)
                    return str(value).strip() if value else None
                value = element.get_attribute(data_type)
                return str(value).strip() if value else None
            except Exception as exc:
                logger.warning(f"Failed to extract {data_type} from element: {exc}")
                return None

        def scrape_page(
            self, url: str, selectors: Dict[str, str], by: str = "xpath"
        ) -> ScrapingResult:
            """Scrape a page using multiple selectors."""
            if not self.navigate_to_url(url):
                return ScrapingResult(
                    success=False,
                    error="Failed to navigate to URL",
                    url=cast(Any, url),
                )

            extracted: Dict[str, Any] = {}
            for field_name, selector in selectors.items():
                try:
                    elements = self.find_elements(selector, by)
                except Exception:
                    elements = []

                if not elements:
                    extracted[field_name] = None
                    continue

                if field_name in {"url", "href", "link"}:
                    extracted[field_name] = self.extract_element_data(
                        elements[0], "href"
                    )
                elif field_name == "body":
                    parts = [
                        t
                        for t in (
                            self.extract_element_data(e, "text") for e in elements
                        )
                        if t
                    ]
                    extracted[field_name] = "\n".join(parts)
                elif field_name == "tags":
                    tags = [
                        t
                        for t in (
                            self.extract_element_data(e, "text") for e in elements
                        )
                        if t
                    ]
                    extracted[field_name] = tags
                else:
                    extracted[field_name] = self.extract_element_data(
                        elements[0], "text"
                    )

            return ScrapingResult(success=True, data=extracted, url=cast(Any, url))

    BrowserClient = _BrowserClientSelenium

except ModuleNotFoundError:
    pass
