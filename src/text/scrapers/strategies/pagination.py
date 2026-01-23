"""
Pagination strategy for discovering article listings.

This module implements dynamic pagination for sites with numbered pages.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from .base import ListingStrategy

logger = logging.getLogger(__name__)


class PaginationStrategy(ListingStrategy):
    """
    Dynamic pagination strategy for sites with numbered pages.

    This strategy automatically detects the last page by checking
    batches of URLs until all URLs in a batch return errors.
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize pagination strategy.

        Expected config keys:
        - url_template: URL template with {num} placeholder
        - start_page: Starting page number (default: 1)
        - batch_size: Number of pages to check per batch (default: 5)
        - start_url: Optional initial URL(s) to scrape before pagination.
                     Can be a single URL string or a list of URLs. (default: None)
        """
        super().__init__(config, max_pages)

        url_template_config = config["url_template"]
        if isinstance(url_template_config, str):
            self.url_templates = [url_template_config]
        else:
            self.url_templates = url_template_config

        self.start_page = config.get("start_page", 1)
        self.step = config.get("step", 1)
        self.batch_size = config.get("batch_size", 5)

        # Handle start_url as either a single URL or a list of URLs
        start_url_config = config.get("start_url", None)
        if start_url_config is None:
            self.start_urls = []
        elif isinstance(start_url_config, str):
            self.start_urls = [start_url_config]
        else:
            self.start_urls = list(start_url_config)

        for template in self.url_templates:
            if "{num}" not in template:
                raise ValueError(
                    f"URL template '{template}' must contain {{num}} placeholder"
                )

    def generate_page_urls(self, start_page: int, count: int) -> List[str]:
        """
        Generate a batch of page URLs.

        Args:
            start_page: Starting page number
            count: Number of URLs to generate

        Returns:
            List of generated URLs
        """
        urls = []
        for template in self.url_templates:
            for i in range(count):
                page_num = start_page + (i * self.step)
                url = template.format(num=page_num)
                urls.append(url)
        return urls

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List, None]:
        """
        Discover URLs and immediately scrape thumbnails in a single request per URL.

        If start_url is provided, scrapes it first before starting pagination.
        This method combines discovery and scraping to ensure each URL is only
        requested once, improving efficiency and reducing server load.

        Args:
            client: HTTP client for making requests
            base_url: Base URL of the website
            thumbnail_selector: CSS selector for thumbnail elements

        Yields:
            Lists of ScrapingResult objects containing thumbnail data
        """
        # Handle start_urls if provided (can be single URL or list)
        if self.start_urls:
            logger.info(
                f"Starting with initial URL scraping: {len(self.start_urls)} URL(s)"
            )
            # Scrape all start_urls first
            start_results = await client.scrape_urls(
                self.start_urls, thumbnail_selector
            )
            successful_start_results = [
                result for result in start_results if result.success
            ]

            if successful_start_results:
                logger.info(
                    f"Successfully scraped start URLs: {len(successful_start_results)} results from {len(self.start_urls)} URL(s)"
                )
                yield successful_start_results
            else:
                logger.warning(f"Failed to scrape start URLs: {self.start_urls}")

        current_page = self.start_page

        logger.info(
            f"Starting combined pagination discovery and scraping from page {current_page}"
        )

        batch_number = 1
        total_pages_processed = 0
        previous_batch_data = None

        while True:
            # Respect max_pages limit if set
            if self.max_pages is not None and total_pages_processed >= self.max_pages:
                logger.info(
                    f"Reached max_pages limit ({self.max_pages}), stopping pagination."
                )
                break

            # Determine how many pages to fetch in this batch
            pages_to_fetch = self.batch_size
            if self.max_pages is not None:
                remaining_pages = self.max_pages - total_pages_processed
                if remaining_pages < pages_to_fetch:
                    pages_to_fetch = remaining_pages

            if pages_to_fetch <= 0:
                break

            # Generate batch of page URLs
            batch_urls = self.generate_page_urls(current_page, pages_to_fetch)

            # Log batch start
            logger.info(
                f"Processing batch {batch_number}: pages {current_page}-{current_page + self.batch_size - 1}"
            )

            # Scrape all URLs in this batch (this will return 404 for non-existent pages)
            scraping_results = await client.scrape_urls(batch_urls, thumbnail_selector)

            # Filter successful results (200 status)
            successful_results = [
                result for result in scraping_results if result.success
            ]

            if not successful_results:
                # No successful pages in this batch - we've reached the end
                logger.info(
                    f"Batch {batch_number}: No accessible pages found. Stopping pagination."
                )
                break

            retrieved_thumbnails = sum(
                [len(result.data) for result in successful_results]
            )
            if retrieved_thumbnails == 0:
                logger.info(
                    f"Batch {batch_number}: No thumbnails found. Stopping pagination."
                )
                break

            # Extract the actual scraped data for comparison
            current_batch_data = [
                result.data for result in successful_results if result.success
            ]

            # Check if current batch data is the same as previous batch (duplicate content)
            if (
                previous_batch_data is not None
                and current_batch_data == previous_batch_data
            ):
                logger.info(
                    f"Batch {batch_number}: Batch data identical to previous batch (same thumbnails repeated). Stopping pagination."
                )
                break

            # Update counters
            total_pages_processed += len(successful_results)

            # Yield the successful scraping results
            yield successful_results

            # Log batch completion
            logger.info(
                f"Batch {batch_number} completed: {len(successful_results)} pages processed, {total_pages_processed} total pages"
            )

            # If we got fewer successful results than the batch size, we might be near the end
            if len(successful_results) < self.batch_size:
                logger.info(
                    f"Batch {batch_number}: Found {len(successful_results)}/{self.batch_size} pages. Might be near end of pagination."
                )

            # Store current batch data for next iteration comparison
            previous_batch_data = current_batch_data

            # Move to next batch
            current_page += self.batch_size * self.step
            batch_number += 1

            # Add a small delay between batches for politeness
            await asyncio.sleep(0.5)

        logger.info("Combined pagination discovery and scraping completed")
