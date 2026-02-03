"""
Follow-link strategy for discovering article listings.

This module implements a strategy for sites without clear pagination URL templates.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
from urllib.parse import urljoin

from .base import ListingStrategy

logger = logging.getLogger(__name__)


class FollowLinkStrategy(ListingStrategy):
    """
    Follow-link strategy for sites without clear pagination URL templates.

    This strategy starts from a start_url and follows links to discover
    subsequent batches of thumbnails. Each page contains a link to the
    next batch, which is found using a CSS selector.
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize follow-link strategy.

        Expected config keys:
        - start_url: Initial URL to start scraping from
        - follow_selector: CSS selector to find the next page link (e.g., "div.next a::attr(href)")
        """
        super().__init__(config, max_pages)

        self.start_url = config.get("start_url")
        if not self.start_url:
            raise ValueError("start_url is required for follow_link strategy")

        self.follow_selector = config.get("follow_selector")
        if not self.follow_selector:
            raise ValueError("follow_selector is required for follow_link strategy")

    def _extract_next_url(self, soup, base_url: str) -> Optional[str]:
        """
        Extract the next page URL from the current page using the follow_selector.

        Args:
            soup: BeautifulSoup object of the current page
            base_url: Base URL for resolving relative URLs

        Returns:
            Absolute URL of the next page, or None if not found
        """
        selector = self.follow_selector

        # Handle ::attr() selectors
        if "::attr(" in selector:
            css_selector, attr_part = selector.split("::attr(")
            attr_name = attr_part.rstrip(")")
            element = soup.select_one(css_selector.strip())
            if element:
                href = element.get(attr_name)
                if href:
                    return urljoin(base_url, href)
        else:
            # Standard selector - get href attribute
            element = soup.select_one(selector)
            if element:
                href = element.get("href")
                if href:
                    return urljoin(base_url, href)

        return None

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List, None]:
        """
        Discover URLs by following links and scrape thumbnails.

        Starts from start_url, scrapes thumbnails, then follows the link
        found by follow_selector to the next page. Continues until no
        next link is found or max_pages is reached.

        Args:
            client: HTTP client for making requests
            base_url: Base URL of the website
            thumbnail_selector: CSS selector for thumbnail elements

        Yields:
            Lists of ScrapingResult objects containing thumbnail data
        """
        current_url = self.start_url
        pages_processed = 0
        visited_urls = set()

        logger.info(f"Starting follow-link discovery from: {current_url}")

        while current_url:
            # Check max_pages limit
            if self.max_pages is not None and pages_processed >= self.max_pages:
                logger.info(f"Reached max_pages limit ({self.max_pages}), stopping.")
                break

            # Avoid infinite loops
            if current_url in visited_urls:
                logger.info(f"Already visited {current_url}, stopping to avoid loop.")
                break

            visited_urls.add(current_url)

            logger.debug(f"Processing page {pages_processed + 1}: {current_url}")

            # Scrape thumbnails from current page
            scraping_results = await client.scrape_urls(
                [current_url], thumbnail_selector
            )

            successful_results = [
                result for result in scraping_results if result.success
            ]

            if successful_results:
                retrieved_thumbnails = sum(
                    len(result.data) for result in successful_results
                )
                if not retrieved_thumbnails:
                    logger.info(f"No thumbnails found on {current_url}.")
                    break
                logger.debug(
                    f"Page {pages_processed + 1}: Found {retrieved_thumbnails} thumbnails"
                )
                yield successful_results

                # Get the soup from the successful result to find next link
                # We need to re-fetch to get the soup for link extraction
                import httpx

                async with httpx.AsyncClient() as http_client:
                    content, status_code = await client.request_url(
                        http_client, current_url
                    )

                if content:
                    soup = client.parse_content(content)
                    next_url = self._extract_next_url(soup, base_url)

                    if next_url:
                        logger.debug(f"Found next page link: {next_url}")
                        current_url = next_url
                    else:
                        logger.info("No next page link found, stopping pagination.")
                        current_url = None
                else:
                    logger.warning(
                        f"Failed to re-fetch page for link extraction: {current_url}"
                    )
                    current_url = None
            else:
                logger.warning(f"Failed to scrape page: {current_url}")
                current_url = None

            pages_processed += 1
            await asyncio.sleep(0.5)

        logger.info(
            f"Follow-link discovery completed. Processed {pages_processed} pages."
        )
