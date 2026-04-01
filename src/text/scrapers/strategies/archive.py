"""
Archive strategy for date-based article discovery.

This module implements strategies for discovering articles from date-based archives.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncGenerator

from .base import ListingStrategy

logger = logging.getLogger(__name__)


class ArchiveStrategy(ListingStrategy):
    """
    Archive strategy for date-based article discovery.

    This strategy iterates through date-based archive pages
    (e.g., /2025/01/, /2025/02/) to discover articles.
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize archive strategy.

        Expected config keys:
        - url_template: URL template with {year} and/or {month} placeholders
        - start_date: Start date (YYYY-MM-DD format)
        - end_date: End date (YYYY-MM-DD format, optional)
        - date_format: Date format for URL ('monthly' or 'daily')
        - batch_size: Number of archive URLs to check per batch (optional, default 10)
        """
        super().__init__(config, max_pages)

        self.url_template = config["url_template"]
        self.date_format = config.get("date_format", "monthly")
        self.batch_size = int(config.get("batch_size", 10))
        if self.batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")

        # Parse start date and normalise based on date format
        self.start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
        if self.date_format == "monthly":
            self.start_date = self.start_date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            self.start_date = self.start_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Determine end date – default to current period if not supplied
        end_date_str = config.get("end_date")
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = datetime.now()

        if self.date_format == "monthly":
            end_date = end_date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

        if end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")

        self.end_date = end_date

        # Validate template placeholders
        required_placeholders = []
        if self.date_format == "monthly":
            required_placeholders = ["{year}", "{month}"]
        elif self.date_format == "daily":
            required_placeholders = ["{year}", "{month}", "{day}"]

        for placeholder in required_placeholders:
            if placeholder not in self.url_template:
                raise ValueError(f"url_template must contain {placeholder} placeholder")

    def generate_date_urls(self) -> List[str]:
        """
        Generate archive URLs based on date range, from newest to oldest.

        Returns:
            List of archive URLs (newest first)
        """
        urls = []
        current_date = self.end_date

        while current_date >= self.start_date:
            if self.date_format == "monthly":
                url = self.url_template.format(
                    year=current_date.year, month=f"{current_date.month:02d}"
                )
                # Move to previous month
                if current_date.month == 1:
                    current_date = current_date.replace(
                        year=current_date.year - 1, month=12
                    )
                else:
                    current_date = current_date.replace(month=current_date.month - 1)

            elif self.date_format == "daily":
                url = self.url_template.format(
                    year=current_date.year,
                    month=f"{current_date.month:02d}",
                    day=f"{current_date.day:02d}",
                )
                # Move to previous day
                current_date -= timedelta(days=1)

            urls.append(url)

        return urls

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List, None]:
        """Discover archive pages and scrape thumbnails in a single pass."""
        archive_urls = self.generate_date_urls()

        # If max_pages is set, take the first N pages (already newest first)
        if self.max_pages is not None and len(archive_urls) > self.max_pages:
            logger.info(
                f"Truncating archive URLs from {len(archive_urls)} to {self.max_pages} (most recent)"
            )
            archive_urls = archive_urls[: self.max_pages]
        logger.info(
            f"Generated {len(archive_urls)} archive URLs from {self.start_date.date()} to {self.end_date.date()}"
        )

        batch_number = 1

        for i in range(0, len(archive_urls), self.batch_size):
            batch = archive_urls[i : i + self.batch_size]
            logger.info(f"Processing archive batch {batch_number}: {len(batch)} URLs")

            scraping_results = await client.scrape_urls(batch, thumbnail_selector)
            successful_results = [
                result for result in scraping_results if result.success
            ]

            if successful_results:
                yield successful_results
            else:
                logger.info(
                    f"Archive batch {batch_number} returned no accessible pages"
                )

            batch_number += 1
            await asyncio.sleep(0.5)


class PaginatedArchiveStrategy(ListingStrategy):
    """
    Paginated archive strategy for date-based article discovery with pagination.

    This strategy iterates through date-based archive pages and for each date,
    paginates through all available pages until no more content is found.
    Useful for sites where each archive date can have multiple pages of articles.
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize paginated archive strategy.

        Expected config keys:
        - start_url: URL template with date placeholders ({year}, {month}, {day} for
                     daily/monthly modes; {date_from} and {date_to} for range mode).
                     This is the first page for each date/window (page 1).
        - url_template: URL template with date placeholders AND {num} for pagination.
        - start_date: Start date (YYYY-MM-DD format)
        - end_date: End date (YYYY-MM-DD format, optional - defaults to today)
        - date_format: Date format for URL ('monthly', 'daily', or 'range')
        - start_page: Starting page number for pagination (default: 2, since start_url is page 1)
        - batch_size: Number of pages to check per batch (default: 5)

        Additional keys for date_format 'range':
        - range_days: Window width in days (required, must be a positive integer)
        - range_date_format: strftime string for formatting {date_from}/{date_to} in URLs
                             (default: '%d.%m.%Y')
        """
        super().__init__(config, max_pages)

        self.start_url_template = config.get("start_url")
        if not self.start_url_template:
            raise ValueError("start_url is required for paginated_archive strategy")

        self.url_template = config.get("url_template")
        if not self.url_template:
            raise ValueError("url_template is required for paginated_archive strategy")

        if "{num}" not in self.url_template:
            raise ValueError(
                "url_template must contain {num} placeholder for pagination"
            )

        self.date_format = config.get("date_format", "daily")
        self.start_page = config.get("start_page", 2)
        self.batch_size = config.get("batch_size", 5)

        # range mode: parse range_days and range_date_format
        if self.date_format == "range":
            range_days = config.get("range_days")
            if not range_days or int(range_days) <= 0:
                raise ValueError(
                    "range_days is required and must be a positive integer for date_format 'range'"
                )
            self.range_days = int(range_days)
            self.range_date_format = config.get("range_date_format", "%d.%m.%Y")

        # Parse start date and normalize based on date format
        self.start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
        if self.date_format == "monthly":
            self.start_date = self.start_date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            self.start_date = self.start_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Determine end date – default to current period if not supplied
        end_date_str = config.get("end_date")
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = datetime.now()

        if self.date_format == "monthly":
            end_date = end_date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

        if end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")

        self.end_date = end_date

        # Validate template placeholders
        required_placeholders = []
        if self.date_format == "monthly":
            required_placeholders = ["{year}", "{month}"]
        elif self.date_format == "daily":
            required_placeholders = ["{year}", "{month}", "{day}"]
        elif self.date_format == "range":
            required_placeholders = ["{date_from}", "{date_to}"]

        for placeholder in required_placeholders:
            if placeholder not in self.start_url_template:
                raise ValueError(f"start_url must contain {placeholder} placeholder")
            if placeholder not in self.url_template:
                raise ValueError(f"url_template must contain {placeholder} placeholder")

    def _format_url(
        self, template: str, date: datetime, page_num: Optional[int] = None
    ) -> str:
        """Format a URL template with date and optional page number."""
        if self.date_format == "monthly":
            url = template.format(
                year=date.year,
                month=f"{date.month:02d}",
                num=page_num if page_num is not None else "",
            )
        elif self.date_format == "range":
            date_from = date - timedelta(days=self.range_days - 1)
            url = template.format(
                date_from=date_from.strftime(self.range_date_format),
                date_to=date.strftime(self.range_date_format),
                num=page_num if page_num is not None else "",
            )
        else:  # daily
            url = template.format(
                year=date.year,
                month=f"{date.month:02d}",
                day=f"{date.day:02d}",
                num=page_num if page_num is not None else "",
            )
        return url

    def _get_previous_date(self, current_date: datetime) -> datetime:
        """Get the previous date based on date_format."""
        if self.date_format == "monthly":
            if current_date.month == 1:
                return current_date.replace(year=current_date.year - 1, month=12)
            else:
                return current_date.replace(month=current_date.month - 1)
        elif self.date_format == "range":
            return current_date - timedelta(days=self.range_days)
        else:  # daily
            return current_date - timedelta(days=1)

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List, None]:
        """
        Discover archive pages with pagination and scrape thumbnails.

        For each date in the range, scrapes the start_url first, then paginates
        through additional pages until:
        - A page returns 404
        - No thumbnails are found on a page
        - The page data is the same as the previous page (duplicate content)

        Args:
            client: HTTP client for making requests
            base_url: Base URL of the website
            thumbnail_selector: CSS selector for thumbnail elements

        Yields:
            Lists of ScrapingResult objects containing thumbnail data
        """
        current_date = self.end_date
        total_dates_processed = 0
        total_pages_scraped = 0

        logger.info(
            f"Starting paginated archive discovery from {self.end_date.date()} to {self.start_date.date()} (newest first)"
        )

        while current_date >= self.start_date:
            # Check max_pages limit (counts dates, not individual pages)
            if self.max_pages is not None and total_dates_processed >= self.max_pages:
                logger.info(f"Reached max_pages limit ({self.max_pages}), stopping.")
                break

            date_str = current_date.strftime("%Y-%m-%d")
            logger.info(f"Processing archive date: {date_str}")

            # First, scrape the start_url (page 1) for this date
            start_url = self._format_url(self.start_url_template, current_date)
            logger.debug(f"Scraping start URL: {start_url}")

            scraping_results = await client.scrape_urls([start_url], thumbnail_selector)
            successful_results = [r for r in scraping_results if r.success]

            if not successful_results:
                logger.info(
                    f"No accessible page for date {date_str}, skipping to previous date"
                )
                current_date = self._get_previous_date(current_date)
                total_dates_processed += 1
                continue

            # Check if we got thumbnails
            has_thumbnails = any(result.data for result in successful_results)

            if not has_thumbnails:
                logger.info(
                    f"No thumbnails found for date {date_str}, skipping to previous date"
                )
                current_date = self._get_previous_date(current_date)
                total_dates_processed += 1
                continue

            # Store the previous page's data for comparison
            previous_page_data = [result.data for result in successful_results]
            yield successful_results
            total_pages_scraped += 1

            # Now paginate through additional pages for this date
            current_page = self.start_page

            while True:
                page_url = self._format_url(
                    self.url_template, current_date, current_page
                )
                logger.debug(f"Scraping page {current_page}: {page_url}")

                page_results = await client.scrape_urls([page_url], thumbnail_selector)
                successful_page_results = [r for r in page_results if r.success]

                # Stop condition 1: 404 or other error
                if not successful_page_results:
                    logger.debug(
                        f"Page {current_page} returned error, stopping pagination for {date_str}"
                    )
                    break

                # Check if we got thumbnails
                has_thumbnails = any(result.data for result in successful_page_results)

                # Stop condition 2: No thumbnails found
                if not has_thumbnails:
                    logger.debug(
                        f"No thumbnails on page {current_page}, stopping pagination for {date_str}"
                    )
                    break

                # Stop condition 3: Same data as previous page (duplicate content)
                current_page_data = [result.data for result in successful_page_results]
                if current_page_data == previous_page_data:
                    logger.debug(
                        f"Page {current_page} has same data as previous page, stopping pagination for {date_str}"
                    )
                    break

                previous_page_data = current_page_data
                yield successful_page_results
                total_pages_scraped += 1

                current_page += 1
                await asyncio.sleep(0.3)

            current_date = self._get_previous_date(current_date)
            total_dates_processed += 1
            await asyncio.sleep(0.5)

        logger.info(
            f"Paginated archive discovery completed. Processed {total_dates_processed} dates, "
            f"scraped {total_pages_scraped} pages"
        )
