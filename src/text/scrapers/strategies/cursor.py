"""
Cursor-based pagination strategy for discovering article listings.

This module implements a strategy for sites that use a "load more" API
with cursor-based pagination. The API returns JSON containing an HTML
fragment, a cursor for the next page, and a has_more flag.

Example: babel.ua uses /api/news/loadmore?after={cursor}
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from bs4 import BeautifulSoup

from .base import ListingStrategy
from ..models import ScrapingResult

logger = logging.getLogger(__name__)


class CursorStrategy(ListingStrategy):
    """
    Cursor-based pagination strategy for sites with "load more" APIs.

    This strategy:
    1. Fetches the start_url as HTML to get initial articles + first cursor
    2. Calls the cursor API repeatedly, extracting HTML fragments from JSON
    3. Stops when has_more is false or no articles are found
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize cursor strategy.

        Expected config keys:
        - start_url: Initial HTML page URL
        - cursor_api: URL template with {cursor} placeholder
        - cursor_selector: CSS selector to extract initial cursor from start page
                          (e.g., ".js-loadmore::attr(data-after)")
        - cursor_json_path: Key in JSON response for next cursor (default: "after")
        - html_json_path: Key in JSON response for HTML fragment (default: "html")
        - has_more_json_path: Key in JSON response for continuation flag (default: "has_more")
        """
        super().__init__(config, max_pages)

        self.start_url = config.get("start_url")
        if not self.start_url:
            raise ValueError("start_url is required for cursor strategy")

        self.cursor_api = config.get("cursor_api")
        if not self.cursor_api:
            raise ValueError("cursor_api is required for cursor strategy")
        if "{cursor}" not in self.cursor_api:
            raise ValueError("cursor_api must contain {cursor} placeholder")

        self.cursor_selector = config.get(
            "cursor_selector", ".js-loadmore::attr(data-after)"
        )
        self.cursor_json_path = config.get("cursor_json_path", "after")
        self.html_json_path = config.get("html_json_path", "html")
        self.has_more_json_path = config.get("has_more_json_path", "has_more")

    def _extract_cursor_from_soup(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the initial cursor value from the start page HTML.

        Supports ::attr() pseudo-selectors for extracting attributes.
        """
        selector = self.cursor_selector

        if "::attr(" in selector:
            css_selector, attr_part = selector.split("::attr(")
            attr_name = attr_part.rstrip(")")
            element = soup.select_one(css_selector.strip())
            if element:
                return element.get(attr_name)
        else:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()

        return None

    def _get_json_value(self, data: Dict, path: str) -> Any:
        """Get a value from a JSON dict using a dot-separated path."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List, None]:
        """
        Discover articles by fetching start page then chaining cursor API calls.

        Yields ScrapingResult lists (same interface as PaginationStrategy).
        """
        import httpx

        # Step 1: Fetch and yield the start page
        logger.info(f"Cursor strategy: fetching start page {self.start_url}")
        start_results = await client.scrape_urls([self.start_url], thumbnail_selector)

        successful = [r for r in start_results if r.success]
        if not successful:
            logger.warning(f"Failed to fetch start page: {self.start_url}")
            return

        yield successful

        # Extract initial cursor from the start page HTML
        async with httpx.AsyncClient() as http_client:
            content, status_code = await client.request_url(http_client, self.start_url)

        if content is None:
            logger.warning("Failed to re-fetch start page for cursor extraction")
            return

        soup = client.parse_content(content)
        cursor = self._extract_cursor_from_soup(soup)

        if not cursor:
            logger.info("No cursor found on start page. Only initial page available.")
            return

        logger.info(f"Initial cursor: {cursor}")

        # Step 2: Chain cursor API calls
        pages_processed = 0

        while cursor:
            if self.max_pages is not None and pages_processed >= self.max_pages:
                logger.info(f"Reached max_pages limit ({self.max_pages})")
                break

            api_url = self.cursor_api.format(cursor=cursor)
            logger.debug(f"Fetching cursor API: {api_url}")

            try:
                async with httpx.AsyncClient() as http_client:
                    raw_content, status_code = await client.request_url(
                        http_client, api_url
                    )

                if raw_content is None:
                    logger.warning(f"Failed to fetch cursor API: {api_url}")
                    break

                # Parse JSON response
                json_data = json.loads(raw_content)

                # Extract HTML fragment
                html_fragment = self._get_json_value(json_data, self.html_json_path)
                if not html_fragment:
                    logger.info("No HTML in cursor API response. Stopping.")
                    break

                # Parse HTML fragment and extract thumbnail elements
                fragment_soup = BeautifulSoup(html_fragment, "html.parser")
                elements = fragment_soup.select(thumbnail_selector)

                if not elements:
                    logger.info("No thumbnails in cursor API response. Stopping.")
                    break

                # Wrap in ScrapingResult to match HTML strategy interface
                result = ScrapingResult(
                    success=True,
                    data=elements,
                    status_code=200,
                    url=api_url,
                )
                yield [result]

                logger.info(
                    f"Cursor page {pages_processed + 1}: " f"{len(elements)} thumbnails"
                )

                # Get next cursor
                next_cursor = self._get_json_value(json_data, self.cursor_json_path)
                has_more = self._get_json_value(json_data, self.has_more_json_path)

                if not has_more or not next_cursor:
                    logger.info("No more pages (has_more=false or no cursor). Done.")
                    break

                cursor = str(next_cursor)
                pages_processed += 1
                await asyncio.sleep(0.5)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from cursor API: {e}")
                break
            except Exception as e:
                logger.error(f"Error in cursor API request: {e}")
                break

        logger.info(
            f"Cursor strategy completed. {pages_processed + 1} pages processed "
            f"(1 start + {pages_processed} API)."
        )
