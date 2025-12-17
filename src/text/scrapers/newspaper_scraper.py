"""
Generic newspaper scraper driven by configuration.

This module provides a NewspaperScraper class that can scrape any newspaper
based on a configuration dictionary, using the appropriate client and strategy.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from urllib.parse import urljoin, urlparse
import httpx
from .client_http import AsyncHttpClient
from .listing_strategies import create_listing_strategy, ApiStrategy
from .models import (
    ThumbnailRecord,
    ArticleRecord,
    NewspaperConfig,
)
from .pipelines.cleaning import apply_cleaning, get_cleaning_func, clean_url
from .pipelines.storage import CSVStorage
from .parser import (
    extract_thumbnail_data_from_element,
    extract_article_data_from_soup,
)

logger = logging.getLogger(__name__)


class NewspaperScraper:
    """
    Generic newspaper scraper driven by configuration.

    This class can scrape any newspaper based on a configuration
    dictionary that specifies selectors, listing strategy, and
    other site-specific parameters.
    """

    def __init__(self, config: Dict[str, Any], urls_from_scratch: bool = False):
        """
        Initialize the newspaper scraper with configuration.

        Args:
            config: Configuration dictionary (validated against NewspaperConfig)
            urls_from_scratch: Whether to discover URLs from scratch (True) or load from urls.csv (False)
        """
        # Validate configuration
        self.config = NewspaperConfig(**config)

        # Basic properties
        self.name = self.config.name
        self.country = self.config.country
        self.base_url = str(self.config.base_url)

        # Store limits from config
        self.max_pages = self.config.max_pages
        self.max_articles = self.config.max_articles

        # Store URL discovery preference
        self.urls_from_scratch = urls_from_scratch

        # Initialize client based on configuration
        self.client_type = self.config.client
        self._http_client: Optional[AsyncHttpClient] = None

        # Initialize listing strategy
        self.listing_strategy = create_listing_strategy(
            self.config.listing, max_pages=self.config.max_pages
        )

        # Selectors for data extraction
        self.thumbnail_selectors = self.config.selectors.thumbnail
        self.article_selectors = self.config.selectors.article

        # Data storage
        self.scraped_thumbnails: List[ThumbnailRecord] = []
        self.scraped_articles: List[ArticleRecord] = []
        self.prefetched_articles: List[ArticleRecord] = []  # Built directly from API JSON when available
        self.failed_urls: List[Dict[str, Any]] = []
        self.failed_news: List[Dict[str, Any]] = []
        self._saved_files = {}  # Track files saved by this scraper

        # Initialize storage system
        self._storage = CSVStorage()

    def _get_http_client(self) -> AsyncHttpClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            # Extract domain for cookie management
            domain = urlparse(self.base_url).netloc

            # Configure client based on auth settings
            auth_config = self.config.auth or {}

            # Get client configuration parameters from config
            concurrency = self.config.concurrency or 10
            rate_limit = self.config.rate_limit or 0.1
            retries = self.config.retries or 3
            retry_seconds = self.config.retry_seconds or 2.0

            # Get headers from config - this was the critical missing piece!
            headers = self.config.headers or {}

            logger.info(f"Creating HTTP client for {self.name}")
            logger.info(f"Domain: {domain}")
            logger.info(f"Loading headers from config")
            logger.info(
                f"Concurrency: {concurrency}, Rate limit: {rate_limit}"
            )
            logger.info(f"Retries: {retries}, Retry delay: {retry_seconds}s")

            self._http_client = AsyncHttpClient(
                parser="html.parser",  # Default to BeautifulSoup
                domain=domain if auth_config else None,
                headers=headers,  # Pass config headers to client
                cookies=auth_config.get("cookies"),
                timeout=60.0,
                max_concurrent=concurrency,
                rate_limit=rate_limit,
                retries=retries,
                retry_seconds=retry_seconds,
            )

        return self._http_client

    def _check_early_stop(self, batch_urls: List[str], existing_urls: Optional[set]) -> bool:
        """
        Check if batch should trigger early stopping.
        
        Early stopping occurs when all URLs in a batch already exist in the
        existing_urls set, indicating no new content to scrape.
        
        Args:
            batch_urls: List of URLs discovered in current batch
            existing_urls: Set of existing URLs to check against
            
        Returns:
            True if early stopping should be triggered, False otherwise
        """
        if not existing_urls or not batch_urls:
            return False
        
        new_urls_in_batch = [url for url in batch_urls if url not in existing_urls]
        if not new_urls_in_batch:
            logger.info(
                f"Early stop: All {len(batch_urls)} URLs in batch already exist in urls.csv. "
                "Stopping thumbnail discovery."
            )
            return True
        else:
            logger.info(
                f"Batch has {len(new_urls_in_batch)} new URLs out of {len(batch_urls)}"
            )
            return False

    async def discover_and_scrape_thumbnails(
        self, existing_urls: Optional[set] = None
    ) -> tuple[List[ThumbnailRecord], bool]:
        """
        Discover listing pages and scrape thumbnails, with smart caching and retry logic.
        
        If existing_urls is provided, discovery stops early when an entire batch
        of discovered URLs is already present in existing_urls.

        Args:
            existing_urls: Optional set of existing URLs to check against for early stopping

        Returns:
            Tuple of (List of ThumbnailRecord objects, early_stop flag)
            - thumbnails: List of newly discovered ThumbnailRecord objects
            - early_stop: True if discovery stopped early because all batch URLs were existing
        """
        client = self._get_http_client()
        thumbnails = []
        thumbnail_selector = self.thumbnail_selectors.container
        
        # Track if we should stop early due to all URLs in batch being existing
        early_stop = False

        # Get the record filter function if it's configured
        record_filter_func_name = self.config.cleaning.get("record_filter")
        record_filter_func = get_cleaning_func(record_filter_func_name) if record_filter_func_name else None

        async for result_batch in self.listing_strategy.discover_and_scrape(
            client, self.base_url, thumbnail_selector
        ):
            # Track URLs discovered in this batch for early stopping check
            batch_urls = []
            
            # Handle API strategy's direct return of dicts
            if isinstance(self.listing_strategy, ApiStrategy):
                for thumb_data in result_batch:
                    try:
                        # Apply record filter if it exists
                        if record_filter_func and not record_filter_func(thumb_data):
                            continue

                        # Handle URL construction from API data (e.g., from an 'id' field)
                        # Ensure URL is absolute before creating the record
                        if thumb_data.get('url'):
                            thumb_data['url'] = clean_url(thumb_data['url'], self.base_url)
                        # Handle URL construction from API data if URL is still missing
                        elif 'url' not in thumb_data or not thumb_data['url']:
                            url_template = self.config.listing.get("url_construction_template")
                            if url_template:
                                thumb_data['url'] = url_template.format(**thumb_data)

                        # Track URL for early stopping check
                        if thumb_data.get('url'):
                            batch_urls.append(str(thumb_data['url']))

                        # Optionally build ArticleRecord directly from API data if 'body' exists
                        if thumb_data.get('body'):
                            article_dict = {
                                'url': thumb_data['url'],
                                'title': thumb_data.get('title', ''),
                                'date': thumb_data.get('date', ''),
                                'body': thumb_data.get('body', ''),
                                'tags': thumb_data.get('tags', []),
                                'source': self.name,
                                'country': self.country,
                            }
                            # Apply cleaning if configured
                            cleaning_config = self.config.cleaning or {}
                            if cleaning_config:
                                article_dict = apply_cleaning(article_dict, cleaning_config, self.base_url)
                            try:
                                article = ArticleRecord(**article_dict)
                                self.prefetched_articles.append(article)
                            except Exception as e:
                                logger.error(f"Failed to create ArticleRecord from API data: {e}")
                                logger.debug(f"Article data: {article_dict}")

                        thumbnail = ThumbnailRecord(**thumb_data)
                        thumbnails.append(thumbnail)
                    except Exception as e:
                        logger.error(f"Failed to create ThumbnailRecord from API data: {e}")
                        logger.error(f"Data: {thumb_data}")
                
                # Check for early stopping
                if self._check_early_stop(batch_urls, existing_urls):
                    early_stop = True
                    break
                
                logger.info(f"Processed API batch: {len(result_batch)} thumbnails")
                continue

            # Existing logic for HTML-based strategies
            for result in result_batch:
                if not result.success:
                    self._add_failed_url(
                        url=result.url,
                        status_code=result.status_code,
                        error=result.error,
                        stage="thumbnail_listing",
                    )
                    continue

                thumbnail_elements = result.data
                if not thumbnail_elements:
                    logger.warning(f"No thumbnails found on {result.url} - retrying")
                    # Simplified for brevity - retry logic would be here
                    continue

                for thumb_elem in thumbnail_elements:
                    thumb_data = extract_thumbnail_data_from_element(
                        thumb_elem,
                        str(result.url),
                        self.thumbnail_selectors,
                        self.base_url,
                        self.config.cleaning,
                    )
                    if thumb_data:
                        try:
                            thumbnail = ThumbnailRecord(**thumb_data)
                            thumbnails.append(thumbnail)
                            # Track URL for early stopping check
                            if thumb_data.get('url'):
                                batch_urls.append(str(thumb_data['url']))
                        except Exception as e:
                            logger.error(f"Failed to create ThumbnailRecord: {e}")
                            logger.error(f"Data: {thumb_data}")

            # Check for early stopping
            if self._check_early_stop(batch_urls, existing_urls):
                early_stop = True
                break

            logger.info(
                f"Processed batch: {len(result_batch)} pages, {len(thumbnails)} total thumbnails"
            )

        if early_stop:
            logger.info(
                f"Early stop triggered. Discovered {len(thumbnails)} new thumbnails before stopping."
            )
        else:
            logger.info(
                f"Total thumbnails discovered and scraped: {len(thumbnails)}"
            )

        # Save thumbnails to CSV file (only if we discovered new ones)
        if thumbnails:
            saved_path = self._storage.save_thumbnails_as_urls(
                thumbnails, self.country, self.name
            )
            if saved_path:
                self._saved_files["urls"] = saved_path

        return thumbnails, early_stop

    async def discover_listing_urls(self) -> List[str]:
        """
        Discover listing page URLs using the configured strategy.

        Returns:
            List of listing page URLs to scrape for thumbnails
        """
        if self.client_type == "http":
            client = self._get_http_client()
        else:
            raise NotImplementedError(
                "Browser client not yet supported for listing discovery"
            )

        all_urls = []

        async for url_batch in self.listing_strategy.discover_urls(
            client, self.base_url
        ):
            all_urls.extend(url_batch)
            logger.info(
                f"Discovered {len(url_batch)} listing URLs (total: {len(all_urls)})"
            )

        logger.info(f"Total listing URLs discovered: {len(all_urls)}")
        return all_urls

    async def scrape_thumbnails_with_retry(
        self, listing_urls: List[str]
    ) -> List[ThumbnailRecord]:
        """
        Scrape thumbnail data from listing pages with retry logic.

        Args:
            listing_urls: List of listing page URLs

        Returns:
            List of ThumbnailRecord objects
        """
        thumbnails = []

        if self.client_type == "http":
            client = self._get_http_client()

            # Scrape all listing pages
            thumbnail_selector = self.thumbnail_selectors.container
            results = await client.scrape_urls(
                listing_urls, thumbnail_selector
            )

            for result in results:
                if not result.success:
                    self._add_failed_url(
                        url=result.url,
                        status_code=result.status_code,
                        error=result.error,
                        stage="thumbnail_listing",
                    )
                    continue

                # Parse the scraped content
                thumbnail_elements = result.data
                if not thumbnail_elements:
                    # No thumbnails found - implement retry logic
                    logger.warning(
                        f"No thumbnails found on {result.url} - starting retry sequence"
                    )

                    # Retry up to 25 times with 2-second delays
                    retry_count = 0
                    max_retries = 25
                    retry_delay = 2.0

                    while retry_count < max_retries:
                        retry_count += 1
                        logger.debug(
                            f"Retry {retry_count}/{max_retries} for {result.url}"
                        )

                        # Wait before retry
                        await asyncio.sleep(retry_delay)

                        # Retry the request
                        try:
                            retry_result = await client.scrape_url(
                                client._http_client,
                                str(result.url),
                                thumbnail_selector,
                            )

                            if retry_result.success and retry_result.data:
                                logger.info(
                                    f"Thumbnails found on retry {retry_count} for {result.url}"
                                )
                                thumbnail_elements = retry_result.data
                                break

                        except Exception as e:
                            logger.debug(
                                f"Retry {retry_count} failed for {result.url}: {e}"
                            )

                    # If still no thumbnails after all retries, mark as failed
                    if not thumbnail_elements:
                        logger.warning(
                            f"No thumbnails found after {max_retries} retries for {result.url}"
                        )
                        self._add_failed_url(
                            url=result.url,
                            status_code=getattr(result, "status_code", None),
                            error=f"No thumbnails found after {max_retries} retries",
                            stage="thumbnail_listing_no_content",
                        )
                        continue

                # Extract data from each thumbnail element
                for thumb_elem in thumbnail_elements:
                    thumb_data = extract_thumbnail_data_from_element(
                        thumb_elem,
                        str(result.url),
                        self.thumbnail_selectors,
                        self.base_url,
                        self.config.cleaning,
                    )
                    if thumb_data:
                        try:
                            thumbnail = ThumbnailRecord(**thumb_data)
                            thumbnails.append(thumbnail)
                        except Exception as e:
                            logger.error(
                                f"Failed to create ThumbnailRecord: {e}"
                            )
                            logger.error(f"Data: {thumb_data}")

        else:
            # Browser client implementation with retry logic
            browser_client = self._get_browser_client()

            try:
                browser_client.start_driver()

                for url in listing_urls:
                    try:
                        if not browser_client.navigate_to_url(url):
                            self._add_failed_url(
                                url=url,
                                error="Failed to navigate",
                                stage="thumbnail_listing",
                            )
                            continue

                        # Find thumbnail elements
                        thumbnail_selector = self.thumbnail_selectors.container
                        thumbnail_elements = browser_client.find_elements(
                            thumbnail_selector
                        )

                        if not thumbnail_elements:
                            # No thumbnails found - implement retry logic
                            logger.warning(
                                f"No thumbnails found on {url} - starting retry sequence"
                            )

                            # Retry up to 25 times with 2-second delays
                            retry_count = 0
                            max_retries = 25
                            retry_delay = 2.0

                            while retry_count < max_retries:
                                retry_count += 1
                                logger.debug(
                                    f"Retry {retry_count}/{max_retries} for {url}"
                                )

                                # Wait before retry
                                await asyncio.sleep(retry_delay)

                                # Retry navigation and element finding
                                try:
                                    if browser_client.navigate_to_url(url):
                                        thumbnail_elements = (
                                            browser_client.find_elements(
                                                thumbnail_selector
                                            )
                                        )
                                        if thumbnail_elements:
                                            logger.info(
                                                f"Thumbnails found on retry {retry_count} for {url}"
                                            )
                                            break
                                except Exception as e:
                                    logger.debug(
                                        f"Retry {retry_count} failed for {url}: {e}"
                                    )

                            # If still no thumbnails after all retries, mark as failed
                            if not thumbnail_elements:
                                logger.warning(
                                    f"No thumbnails found after {max_retries} retries for {url}"
                                )
                                self._add_failed_url(
                                    url=url,
                                    error=f"No thumbnails found after {max_retries} retries",
                                    stage="thumbnail_listing_no_content",
                                )
                                continue

                        # Extract data from each thumbnail
                        for thumb_elem in thumbnail_elements:
                            try:
                                thumb_data = (
                                    extract_thumbnail_data_from_element(
                                        thumb_elem,
                                        url,
                                        self.thumbnail_selectors,
                                        self.base_url,
                                        self.config.cleaning,
                                    )
                                )
                                if thumb_data:
                                    try:
                                        thumbnail = ThumbnailRecord(
                                            **thumb_data
                                        )
                                        thumbnails.append(thumbnail)
                                    except Exception as e:
                                        logger.error(
                                            f"Failed to create ThumbnailRecord: {e}"
                                        )
                                        logger.error(f"Data: {thumb_data}")
                            except Exception as e:
                                logger.error(
                                    f"Error processing thumbnail element: {e}"
                                )

                    except Exception as e:
                        self._add_failed_url(
                            url=url, error=str(e), stage="thumbnail_listing"
                        )

            finally:
                browser_client.close_driver()

        logger.info(
            f"Scraped {len(thumbnails)} thumbnails from {len(listing_urls)} listing pages"
        )
        self.scraped_thumbnails = thumbnails
        return thumbnails

    async def scrape_thumbnails(
        self, listing_urls: List[str]
    ) -> List[ThumbnailRecord]:
        """
        Scrape thumbnail data from listing pages (legacy method without retry).

        Args:
            listing_urls: List of listing page URLs

        Returns:
            List of ThumbnailRecord objects
        """
        # Delegate to the retry version for consistency
        return await self.scrape_thumbnails_with_retry(listing_urls)

    async def scrape_articles(
        self, thumbnails: List[ThumbnailRecord]
    ) -> Dict[str, Any]:
        """
        Scrape full article content from thumbnail URLs with streaming CSV writes.

        Articles are written to CSV as they are scraped, not accumulated in memory.

        Args:
            thumbnails: List of ThumbnailRecord objects

        Returns:
            Dictionary with scraping statistics (articles_scraped, failed_count, etc.)
        """
        article_urls = [str(thumb.url) for thumb in thumbnails]
        articles_scraped = 0
        articles_failed = 0

        if self.client_type == "http":
            client = self._get_http_client()

            # Import tqdm for progress tracking
            from tqdm.asyncio import tqdm

            # Scrape articles with tqdm progress bar
            logger.info(f"Scraping {len(article_urls)} articles...")

            # Process with tqdm progress bar
            async with httpx.AsyncClient() as http_client:
                for i, thumbnail in enumerate(
                    tqdm(thumbnails, desc="Scraping articles")
                ):
                    try:
                        # Fetch article page HTML content
                        content, status_code = await client.request_url(
                            http_client, str(thumbnail.url)
                        )

                        if content is None:
                            self._add_failed_news(
                                url=thumbnail.url,
                                status_code=status_code,
                                error="Failed to retrieve content",
                                stage="article_content",
                            )
                            articles_failed += 1
                            continue

                        # Parse the HTML content
                        soup = client.parse_content(content)

                        # Extract article body and tags using the new extraction function
                        article_content = extract_article_data_from_soup(
                            soup,
                            str(thumbnail.url),
                            self.article_selectors,
                            self.base_url,
                            self.config.cleaning,
                        )

                        # Combine thumbnail data with extracted article content
                        article_data = {
                            "url": str(thumbnail.url),
                            "title": thumbnail.title,
                            "date": (
                                thumbnail.date
                                if thumbnail.date
                                else article_content.get("date", "")
                            ),
                            "body": article_content.get("body", ""),
                            "tags": article_content.get("tags", []),
                            "source": self.name,
                            "country": self.country,
                        }

                        # Apply cleaning functions to article data if configured
                        cleaning_config = self.config.cleaning
                        if cleaning_config:
                            article_data = apply_cleaning(
                                article_data, cleaning_config, self.base_url
                            )

                        article = ArticleRecord(**article_data)
                        
                        # Stream write to CSV instead of accumulating in memory
                        self._storage.append_article(
                            article, self.country, self.name
                        )
                        articles_scraped += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to scrape article {thumbnail.url}: {e}"
                        )
                        articles_failed += 1

        else:
            # Browser client implementation would go here
            pass

        logger.info(
            f"Scraped {articles_scraped} articles from {len(thumbnails)} thumbnails "
            f"({articles_failed} failed)"
        )

        # Return statistics instead of article list
        return {
            "articles_scraped": articles_scraped,
            "articles_failed": articles_failed,
            "total_attempted": len(thumbnails),
        }

    async def run_full_scrape(self) -> Dict[str, Any]:
        """
        Run a complete scraping operation with streaming CSV writes.

        Articles are written to CSV as they are scraped, not accumulated in memory.
        
        Discovery stops early when an entire batch of discovered URLs is already
        present in urls.csv, then proceeds to scrape only missing articles.

        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting full scrape for {self.name} ({self.country})")

        try:
            # Load existing thumbnail URLs for early stopping during discovery
            existing_thumbnail_urls = self._storage.get_existing_thumbnail_urls(
                self.country, self.name
            )
            if existing_thumbnail_urls:
                logger.info(
                    f"Loaded {len(existing_thumbnail_urls)} existing URLs from urls.csv for early stopping check"
                )
            
            # Initialize CSV file with headers before scraping
            csv_path = self._storage.initialize_csv(self.country, self.name)
            self._saved_files["articles"] = csv_path
            logger.info(f"Initialized CSV file for streaming writes: {csv_path}")

            # Step 1 & 2 Combined: Discover and scrape thumbnails in one pass
            # This ensures each URL is only requested once
            # Pass existing URLs for early stopping when entire batch is already present
            new_thumbnails, early_stop = await self.discover_and_scrape_thumbnails(
                existing_urls=existing_thumbnail_urls if existing_thumbnail_urls else None
            )

            # If early stop occurred, load existing thumbnails and merge with new ones
            if early_stop:
                logger.info("Early stop occurred - loading existing thumbnails from urls.csv")
                existing_thumbnails = self._storage.load_urls_from_csv(
                    self.country, self.name
                )
                if existing_thumbnails:
                    # Create a set of new URLs for deduplication
                    new_urls_set = {str(t.url) for t in new_thumbnails}
                    # Add existing thumbnails that aren't in the new set
                    for thumb in existing_thumbnails:
                        if str(thumb.url) not in new_urls_set:
                            new_thumbnails.append(thumb)
                    logger.info(
                        f"Merged thumbnails: {len(new_thumbnails)} total "
                        f"({len(existing_thumbnails)} existing + new discoveries)"
                    )
            
            thumbnails = new_thumbnails

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating thumbnails from {len(thumbnails)} to {self.max_articles} based on max_articles config"
                )
                thumbnails = thumbnails[: self.max_articles]

            # Filter thumbnails to only scrape articles missing from news.csv
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            if existing_article_urls:
                original_count = len(thumbnails)
                thumbnails_to_scrape = [
                    t for t in thumbnails if str(t.url) not in existing_article_urls
                ]
                skipped_count = original_count - len(thumbnails_to_scrape)
                logger.info(
                    f"Filtered thumbnails: {len(thumbnails_to_scrape)} to scrape, "
                    f"{skipped_count} already in news.csv"
                )
            else:
                thumbnails_to_scrape = thumbnails

            # Step 3: Build articles with streaming CSV writes
            articles_stats = {}
            if self.prefetched_articles:
                # Filter prefetched articles to only include those not already in news.csv
                prefetched_to_write = [
                    a for a in self.prefetched_articles 
                    if str(a.url) not in existing_article_urls
                ] if existing_article_urls else self.prefetched_articles
                
                logger.info(f"Using {len(prefetched_to_write)} prefetched articles from API JSON; skipping HTML article scraping")
                # Stream write prefetched articles to CSV
                for article in prefetched_to_write:
                    self._storage.append_article(article, self.country, self.name)
                articles_stats = {
                    "articles_scraped": len(prefetched_to_write),
                    "articles_failed": 0,
                    "total_attempted": len(self.prefetched_articles),
                }
            else:
                # Scrape articles with streaming writes (only missing articles)
                articles_stats = await self.scrape_articles(thumbnails_to_scrape)

            # Compile results - serialize thumbnails for metadata
            try:
                logger.info("Creating results dictionary...")

                # Serialize thumbnails for metadata
                serialized_thumbnails = []
                for i, thumb in enumerate(thumbnails):
                    try:
                        serialized_thumb = self._storage.serialize_for_json(
                            thumb.model_dump()
                        )
                        serialized_thumbnails.append(serialized_thumb)
                    except Exception as e:
                        logger.error(f"Failed to serialize thumbnail {i}: {e}")
                        logger.error(f"Thumbnail type: {type(thumb)}")
                        raise

                # Serialize failed URLs
                try:
                    serialized_errors = self._storage.serialize_for_json(
                        self.failed_urls
                    )
                except Exception as e:
                    logger.error(f"Failed to serialize failed_urls: {e}")
                    logger.error(f"Failed URLs count: {len(self.failed_urls)}")
                    raise

                results = {
                    "success": True,
                    "newspaper": self.name,
                    "country": self.country,
                    "statistics": {
                        "thumbnails_found": len(thumbnails),
                        "articles_scraped": articles_stats.get("articles_scraped", 0),
                        "articles_failed": articles_stats.get("articles_failed", 0),
                        "failed_urls": len(self.failed_urls),
                        "failed_news": len(self.failed_news),
                    },
                    "data": {
                        "thumbnails": serialized_thumbnails,
                        # Note: articles are now in CSV, not in memory
                        "articles": "(streamed to CSV)",
                    },
                    "errors": serialized_errors,
                }

                logger.info("Results dictionary created successfully")

            except Exception as e:
                logger.error(f"Failed to create results dictionary: {e}")
                raise

            # Save failed URLs and news if any - let storage handle serialization
            if self.failed_urls:
                saved_path = self._storage.save_failed_urls(
                    self.failed_urls, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            if self.failed_news:
                saved_path = self._storage.save_failed_news(
                    self.failed_news, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_news"] = saved_path

            # Save metadata - let storage handle serialization
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.name
                )
                if saved_path:
                    self._saved_files["metadata"] = saved_path
            except Exception as e:
                logger.error(f"Failed to save metadata: {e}")
                raise

            logger.info(
                f"Scraping completed for {self.name}: {articles_stats.get('articles_scraped', 0)} articles scraped"
            )
            return results

        except Exception as e:
            logger.error(f"Scraping failed for {self.name}: {e}")
            error_results = {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "error": str(e),
                "statistics": {
                    "listing_urls": 0,
                    "thumbnails_found": len(self.scraped_thumbnails),
                    "articles_scraped": 0,
                    "failed_urls": len(self.failed_urls),
                    "failed_news": len(self.failed_news),
                },
            }
            # Ensure error results are also JSON serializable
            return self._storage.serialize_for_json(error_results)

    async def run_update_scrape(self) -> Dict[str, Any]:
        """
        Run an update scraping operation with streaming CSV writes.

        This mode scrapes all URLs but only processes articles that don't already exist
        in the news.csv file, making it efficient for incremental updates.
        New articles are streamed to CSV as they are scraped.

        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting update scrape for {self.name} ({self.country})")

        try:
            # Step 1: Load existing URLs for early stopping and article filtering
            existing_thumbnail_urls = self._storage.get_existing_thumbnail_urls(
                self.country, self.name
            )
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            logger.info(
                f"Found {len(existing_thumbnail_urls)} existing thumbnail URLs, "
                f"{len(existing_article_urls)} existing articles to skip"
            )

            # Reset prefetched articles for this run
            self.prefetched_articles = []

            # Step 2: Discover and scrape thumbnails
            if self.urls_from_scratch:
                # Full discovery from scratch - ignore urls.csv, no early stopping
                logger.info("urls_from_scratch=True: Discovering all thumbnails from scratch, ignoring urls.csv")
                thumbnails, _ = await self.discover_and_scrape_thumbnails(existing_urls=None)
                logger.info(f"Discovered {len(thumbnails)} thumbnails from scratch")
            else:
                # Load existing urls.csv and discover new thumbnails with early stopping
                logger.info("urls_from_scratch=False: Loading existing urls.csv and discovering new thumbnails")
                existing_thumbnails = self._storage.load_urls_from_csv(self.country, self.name)
                
                if existing_thumbnails:
                    logger.info(f"Loaded {len(existing_thumbnails)} existing thumbnails from urls.csv")
                    # Discover new thumbnails with early stopping when batch is all known
                    new_thumbnails, early_stop = await self.discover_and_scrape_thumbnails(
                        existing_urls=existing_thumbnail_urls if existing_thumbnail_urls else None
                    )
                    # Merge new discoveries with existing thumbnails
                    discovered_urls_set = {str(t.url) for t in new_thumbnails}
                    for thumb in existing_thumbnails:
                        if str(thumb.url) not in discovered_urls_set:
                            new_thumbnails.append(thumb)
                    thumbnails = new_thumbnails
                    logger.info(f"Merged: {len(thumbnails)} total thumbnails ({len(new_thumbnails) - len(existing_thumbnails)} new)")
                else:
                    logger.info("urls.csv not found. Discovering all thumbnails from scratch")
                    thumbnails, _ = await self.discover_and_scrape_thumbnails(existing_urls=None)
                    logger.info(f"Discovered {len(thumbnails)} thumbnails")

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating thumbnails from {len(thumbnails)} to {self.max_articles} based on max_articles config"
                )
                thumbnails = thumbnails[: self.max_articles]

            # Step 3: Filter thumbnails to only include new articles
            thumbnails_to_scrape = []
            skipped_count = 0
            new_prefetched_articles: List[ArticleRecord] = []
            prefetched_by_url = {
                str(article.url): article for article in self.prefetched_articles
            }

            for thumbnail in thumbnails:
                thumbnail_url = str(thumbnail.url)
                if thumbnail_url not in existing_article_urls:
                    thumbnails_to_scrape.append(thumbnail)
                    if thumbnail_url in prefetched_by_url:
                        new_prefetched_articles.append(prefetched_by_url[thumbnail_url])
                else:
                    skipped_count += 1

            logger.info(
                f"Filtered thumbnails: {len(thumbnails_to_scrape)} new, {skipped_count} already exist"
            )

            # Step 4: Stream new articles directly to CSV
            new_articles_count = 0
            new_articles_failed = 0

            # Stream prefetched articles directly to CSV
            if new_prefetched_articles:
                logger.info(
                    f"Using {len(new_prefetched_articles)} prefetched articles from API JSON; streaming to CSV"
                )
                for article in new_prefetched_articles:
                    self._storage.append_article(article, self.country, self.name)
                    new_articles_count += 1

            # Identify thumbnails that still require HTML scraping
            remaining_thumbnails = [
                thumb
                for thumb in thumbnails_to_scrape
                if str(thumb.url) not in prefetched_by_url
            ]

            if remaining_thumbnails:
                # Scrape remaining articles with streaming writes
                scrape_stats = await self.scrape_articles(remaining_thumbnails)
                new_articles_count += scrape_stats.get("articles_scraped", 0)
                new_articles_failed += scrape_stats.get("articles_failed", 0)
                logger.info(
                    f"Scraped {scrape_stats.get('articles_scraped', 0)} new articles from HTML pages"
                )
            elif not new_prefetched_articles:
                logger.info("No new articles to scrape")

            # Save thumbnails (all discovered thumbnails, not just new ones)
            saved_path = self._storage.save_thumbnails_as_urls(
                thumbnails, self.country, self.name
            )
            if saved_path:
                self._saved_files["urls"] = saved_path

            # Mark articles file as saved (already streamed)
            csv_path = self._storage.get_newspaper_dir(self.country, self.name) / "news.csv"
            if csv_path.exists():
                self._saved_files["articles"] = csv_path

            # Compile results - ensure all HttpUrl objects are converted to strings
            try:
                logger.info("Creating update results dictionary...")

                # Serialize thumbnails for metadata
                serialized_thumbnails = []
                for i, thumb in enumerate(thumbnails):
                    try:
                        serialized_thumb = self._storage.serialize_for_json(
                            thumb.model_dump()
                        )
                        serialized_thumbnails.append(serialized_thumb)
                    except Exception as e:
                        logger.error(f"Failed to serialize thumbnail {i}: {e}")
                        raise

                # Serialize failed URLs
                try:
                    serialized_errors = self._storage.serialize_for_json(
                        self.failed_urls
                    )
                except Exception as e:
                    logger.error(f"Failed to serialize failed_urls: {e}")
                    raise

                results = {
                    "success": True,
                    "newspaper": self.name,
                    "country": self.country,
                    "mode": "update",
                    "statistics": {
                        "thumbnails_found": len(thumbnails),
                        "existing_articles_skipped": skipped_count,
                        "articles_scraped": new_articles_count,
                        "articles_failed": new_articles_failed,
                        "total_articles_after_update": len(existing_article_urls)
                        + new_articles_count,
                        "failed_urls": len(self.failed_urls),
                        "failed_news": len(self.failed_news),
                    },
                    "data": {
                        "thumbnails": serialized_thumbnails,
                        # Note: new articles are now streamed to CSV
                        "new_articles": "(streamed to CSV)",
                    },
                    "errors": serialized_errors,
                }

                logger.info("Update results dictionary created successfully")

            except Exception as e:
                logger.error(
                    f"Failed to create update results dictionary: {e}"
                )
                raise

            # Save failed URLs and news if any
            if self.failed_urls:
                saved_path = self._storage.save_failed_urls(
                    self.failed_urls, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            if self.failed_news:
                saved_path = self._storage.save_failed_news(
                    self.failed_news, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_news"] = saved_path

            # Save metadata
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.name, metadata_type="update"
                )
                if saved_path:
                    self._saved_files["metadata"] = saved_path
            except Exception as e:
                logger.error(f"Failed to save update metadata: {e}")
                raise

            logger.info(
                f"Update scrape completed for {self.name}: {new_articles_count} new articles added"
            )
            return results

        except Exception as e:
            logger.error(f"Update scraping failed for {self.name}: {e}")
            error_results = {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "update",
                "error": str(e),
                "statistics": {
                    "thumbnails_found": len(self.scraped_thumbnails),
                    "new_articles_scraped": 0,
                    "failed_urls": len(self.failed_urls),
                    "failed_news": len(self.failed_news),
                },
            }
            # Ensure error results are also JSON serializable
            return self._storage.serialize_for_json(error_results)

    async def run_scrape_from_urls(self) -> Dict[str, Any]:
        """
        Run scraping using pre-loaded URLs from urls.csv file.

        This mode skips the expensive thumbnail discovery phase and uses
        cached URLs from a previous scrape. Falls back to full discovery
        if urls.csv doesn't exist.

        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting scrape from URLs for {self.name} ({self.country})")

        try:
            # Initialize CSV file with headers before scraping
            csv_path = self._storage.initialize_csv(self.country, self.name)
            self._saved_files["articles"] = csv_path
            logger.info(f"Initialized CSV file for streaming writes: {csv_path}")

            # Step 1: Load existing URLs for article filtering
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            existing_thumbnail_urls = self._storage.get_existing_thumbnail_urls(
                self.country, self.name
            )
            
            # Step 2: Discover and scrape thumbnails
            if self.urls_from_scratch:
                # Full discovery from scratch - ignore urls.csv, no early stopping
                logger.info("urls_from_scratch=True: Discovering all thumbnails from scratch, ignoring urls.csv")
                thumbnails, _ = await self.discover_and_scrape_thumbnails(existing_urls=None)
                logger.info(f"Discovered {len(thumbnails)} thumbnails from scratch")
            else:
                # Load existing urls.csv and discover new thumbnails with early stopping
                logger.info("urls_from_scratch=False: Loading existing urls.csv and discovering new thumbnails")
                existing_thumbnails = self._storage.load_urls_from_csv(self.country, self.name)
                
                if existing_thumbnails:
                    logger.info(f"Loaded {len(existing_thumbnails)} existing thumbnails from urls.csv")
                    # Discover new thumbnails with early stopping when batch is all known
                    new_thumbnails, early_stop = await self.discover_and_scrape_thumbnails(
                        existing_urls=existing_thumbnail_urls if existing_thumbnail_urls else None
                    )
                    print(new_thumbnails)
                    # Merge new discoveries with existing thumbnails
                    discovered_urls_set = {str(t.url) for t in new_thumbnails}
                    for thumb in existing_thumbnails:
                        if str(thumb.url) not in discovered_urls_set:
                            new_thumbnails.append(thumb)
                    thumbnails = new_thumbnails
                    logger.info(f"Merged: {len(thumbnails)} total thumbnails ({len(new_thumbnails) - len(existing_thumbnails)} new)")
                else:
                    logger.info("urls.csv not found. Discovering all thumbnails from scratch")
                    thumbnails, _ = await self.discover_and_scrape_thumbnails(existing_urls=None)
                    logger.info(f"Discovered {len(thumbnails)} thumbnails")

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating thumbnails from {len(thumbnails)} to {self.max_articles} based on max_articles config"
                )
                thumbnails = thumbnails[: self.max_articles]

            # Filter thumbnails to only scrape articles missing from news.csv
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            if existing_article_urls:
                original_count = len(thumbnails)
                thumbnails_to_scrape = [
                    t for t in thumbnails if str(t.url) not in existing_article_urls
                ]
                skipped_count = original_count - len(thumbnails_to_scrape)
                logger.info(
                    f"Filtered thumbnails: {len(thumbnails_to_scrape)} to scrape, "
                    f"{skipped_count} already in news.csv"
                )
            else:
                thumbnails_to_scrape = thumbnails

            # Step 2: Build articles with streaming CSV writes
            articles_stats = {}
            if self.prefetched_articles:
                # Filter prefetched articles to only include those not already in news.csv
                prefetched_to_write = [
                    a for a in self.prefetched_articles 
                    if str(a.url) not in existing_article_urls
                ] if existing_article_urls else self.prefetched_articles
                
                logger.info(f"Using {len(prefetched_to_write)} prefetched articles from API JSON; skipping HTML article scraping")
                # Stream write prefetched articles to CSV
                for article in prefetched_to_write:
                    self._storage.append_article(article, self.country, self.name)
                articles_stats = {
                    "articles_scraped": len(prefetched_to_write),
                    "articles_failed": 0,
                    "total_attempted": len(self.prefetched_articles),
                }
            else:
                # Scrape articles with streaming writes (only missing articles)
                articles_stats = await self.scrape_articles(thumbnails_to_scrape)

            # Compile results - serialize thumbnails for metadata
            try:
                logger.info("Creating results dictionary...")

                # Serialize thumbnails for metadata
                serialized_thumbnails = []
                for i, thumb in enumerate(thumbnails):
                    try:
                        serialized_thumb = self._storage.serialize_for_json(
                            thumb.model_dump()
                        )
                        serialized_thumbnails.append(serialized_thumb)
                    except Exception as e:
                        logger.error(f"Failed to serialize thumbnail {i}: {e}")
                        logger.error(f"Thumbnail type: {type(thumb)}")
                        raise

                # Serialize failed URLs
                try:
                    serialized_errors = self._storage.serialize_for_json(
                        self.failed_urls
                    )
                except Exception as e:
                    logger.error(f"Failed to serialize failed_urls: {e}")
                    logger.error(f"Failed URLs count: {len(self.failed_urls)}")
                    raise

                results = {
                    "success": True,
                    "newspaper": self.name,
                    "country": self.country,
                    "mode": "from_urls",
                    "statistics": {
                        "thumbnails_found": len(thumbnails),
                        "articles_scraped": articles_stats.get("articles_scraped", 0),
                        "articles_failed": articles_stats.get("articles_failed", 0),
                        "failed_urls": len(self.failed_urls),
                        "failed_news": len(self.failed_news),
                    },
                    "data": {
                        "thumbnails": serialized_thumbnails,
                        # Note: articles are now in CSV, not in memory
                        "articles": "(streamed to CSV)",
                    },
                    "errors": serialized_errors,
                }

                logger.info("Results dictionary created successfully")

            except Exception as e:
                logger.error(f"Failed to create results dictionary: {e}")
                raise

            # Save failed URLs and news if any - let storage handle serialization
            if self.failed_urls:
                saved_path = self._storage.save_failed_urls(
                    self.failed_urls, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            if self.failed_news:
                saved_path = self._storage.save_failed_news(
                    self.failed_news, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_news"] = saved_path

            # Save metadata - let storage handle serialization
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.name, metadata_type="from_urls"
                )
                if saved_path:
                    self._saved_files["metadata"] = saved_path
            except Exception as e:
                logger.error(f"Failed to save metadata: {e}")
                raise

            logger.info(
                f"Scraping from URLs completed for {self.name}: {articles_stats.get('articles_scraped', 0)} articles scraped"
            )
            return results

        except Exception as e:
            logger.error(f"Scraping from URLs failed for {self.name}: {e}")
            error_results = {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "from_urls",
                "error": str(e),
                "statistics": {
                    "thumbnails_found": len(self.scraped_thumbnails),
                    "articles_scraped": 0,
                    "failed_urls": len(self.failed_urls),
                    "failed_news": len(self.failed_news),
                },
            }
            # Ensure error results are also JSON serializable
            return self._storage.serialize_for_json(error_results)

    def _add_failed_url(
        self,
        url: Any,
        status_code: Any = None,
        error: str = None,
        stage: str = None,
    ):
        """
        Safely add a failed URL with automatic serialization of HttpUrl objects.

        Args:
            url: URL that failed (can be HttpUrl or string)
            status_code: HTTP status code if available
            error: Error message
            stage: Stage where the failure occurred
        """
        failed_entry = {
            "url": str(url) if url else None,
            "status_code": status_code,
            "error": error,
            "stage": stage,
        }
        self.failed_urls.append(failed_entry)

    def _add_failed_news(
        self,
        url: Any,
        status_code: Any = None,
        error: str = None,
        stage: str = None,
    ):
        """
        Safely add a failed news article with automatic serialization of HttpUrl objects.

        Args:
            url: URL that failed (can be HttpUrl or string)
            status_code: HTTP status code if available
            error: Error message
            stage: Stage where the failure occurred
        """
        failed_entry = {
            "url": str(url) if url else None,
            "status_code": status_code,
            "error": error,
            "stage": stage,
        }
        self.failed_news.append(failed_entry)

    def cleanup(self):
        """Clean up resources."""
        if self._browser_client:
            self._browser_client.close_driver()

        # HTTP client cleanup is handled automatically by httpx

