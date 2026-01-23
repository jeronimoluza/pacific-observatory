"""
Slim newspaper scraper orchestrator.

This module provides the main NewspaperScraper class that orchestrates
discovery and extraction operations through specialized orchestrators.

This is Phase 1 of the refactoring - the orchestrators delegate back to
the original methods for now. Full migration will happen in Phase 2.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
import httpx
from .client_http import AsyncHttpClient
from .client_browser import BrowserClient
from .strategies import create_listing_strategy, ApiStrategy
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
from .discovery import DiscoveryOrchestrator
from .extraction import ExtractionOrchestrator

logger = logging.getLogger(__name__)


class NewspaperScraper:
    """
    Generic newspaper scraper driven by configuration.

    This class can scrape any newspaper based on a configuration
    dictionary that specifies selectors, listing strategy, and
    other site-specific parameters.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the newspaper scraper with configuration.

        Args:
            config: Configuration dictionary (validated against NewspaperConfig)
        """
        # Validate configuration
        self.config = NewspaperConfig(**config)

        # Basic properties
        self.name = self.config.name
        self.country = self.config.country
        self.base_url = str(self.config.base_url)
        self.language = self.config.language or "en"

        # Store limits from config
        self.max_pages = self.config.max_pages
        self.max_articles = self.config.max_articles

        # Initialize client based on configuration
        self.client_type = self.config.client
        self._http_client: Optional[AsyncHttpClient] = None
        self._browser_client: Optional[BrowserClient] = None

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
        self.prefetched_articles: List[
            ArticleRecord
        ] = []  # Built directly from API JSON when available
        self.failed_urls: List[Dict[str, Any]] = []
        self.failed_news: List[Dict[str, Any]] = []
        self._saved_files = {}  # Track files saved by this scraper

        # Initialize storage system
        self._storage = CSVStorage()

        # Initialize orchestrators
        self.discovery_orchestrator = DiscoveryOrchestrator(self)
        self.extraction_orchestrator = ExtractionOrchestrator(self)

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
            logger.info("Loading headers from config")
            logger.info(f"Concurrency: {concurrency}, Rate limit: {rate_limit}")
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

    def _get_browser_client(self) -> BrowserClient:
        """Get or create browser client."""
        if self._browser_client is None:
            self._browser_client = BrowserClient(
                headless=True, timeout=20.0, page_load_timeout=30.0
            )

        return self._browser_client

    # ==========================================================================
    # Original methods (prefixed with _original_ for Phase 1)
    # These will be migrated to orchestrators in Phase 2
    # ==========================================================================

    async def _original_discover_and_scrape_thumbnails(self) -> List[ThumbnailRecord]:
        """
        Discover listing pages and scrape thumbnails, with smart caching and retry logic.

        Returns:
            List of ThumbnailRecord objects
        """
        client = self._get_http_client()
        thumbnails = []
        thumbnail_selector = self.thumbnail_selectors.container

        # Get the record filter function if it's configured
        record_filter_func_name = self.config.cleaning.get("record_filter")
        record_filter_func = (
            get_cleaning_func(record_filter_func_name)
            if record_filter_func_name
            else None
        )

        async for result_batch in self.listing_strategy.discover_and_scrape(
            client, self.base_url, thumbnail_selector
        ):
            # Handle API strategy's direct return of dicts
            if isinstance(self.listing_strategy, ApiStrategy):
                for thumb_data in result_batch:
                    try:
                        # Apply record filter if it exists
                        if record_filter_func and not record_filter_func(thumb_data):
                            continue

                        # Handle URL construction from API data (e.g., from an 'id' field)
                        # Ensure URL is absolute before creating the record
                        if thumb_data.get("url"):
                            thumb_data["url"] = clean_url(
                                thumb_data["url"], self.base_url
                            )
                        # Handle URL construction from API data if URL is still missing
                        elif "url" not in thumb_data or not thumb_data["url"]:
                            url_template = self.config.listing.get(
                                "url_construction_template"
                            )
                            if url_template:
                                thumb_data["url"] = url_template.format(**thumb_data)

                        # Apply cleaning to thumbnail data before creating record
                        cleaning_config = self.config.cleaning or {}
                        if cleaning_config:
                            thumb_data = apply_cleaning(
                                thumb_data, cleaning_config, self.base_url
                            )

                        # Optionally build ArticleRecord directly from API data if 'body' exists
                        if thumb_data.get("body"):
                            article_dict = {
                                "url": thumb_data["url"],
                                "title": thumb_data.get("title", ""),
                                "date": thumb_data.get("date", ""),
                                "body": thumb_data.get("body", ""),
                                "tags": thumb_data.get("tags", []),
                                "source": self.name,
                                "country": self.country,
                                "language": self.language,
                            }
                            # Cleaning already applied to thumb_data above
                            try:
                                article = ArticleRecord(**article_dict)
                                self.prefetched_articles.append(article)
                            except Exception as e:
                                logger.error(
                                    f"Failed to create ArticleRecord from API data: {e}"
                                )
                                logger.debug(f"Article data: {article_dict}")

                        thumbnail = ThumbnailRecord(**thumb_data)
                        thumbnails.append(thumbnail)
                    except Exception as e:
                        logger.error(
                            f"Failed to create ThumbnailRecord from API data: {e}"
                        )
                        logger.error(f"Data: {thumb_data}")
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
                        except Exception as e:
                            logger.error(f"Failed to create ThumbnailRecord: {e}")
                            logger.error(f"Data: {thumb_data}")

            logger.info(
                f"Processed batch: {len(result_batch)} pages, {len(thumbnails)} total thumbnails"
            )

        logger.info(f"Total thumbnails discovered and scraped: {len(thumbnails)}")

        # Save thumbnails to JSONL file
        saved_path = self._storage.save_thumbnails_as_urls(
            thumbnails, self.country, self.name
        )
        if saved_path:
            self._saved_files["urls"] = saved_path

        return thumbnails

    async def _original_discover_listing_urls(self) -> List[str]:
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

    async def _original_scrape_thumbnails_with_retry(
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
            results = await client.scrape_urls(listing_urls, thumbnail_selector)

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
                            logger.error(f"Failed to create ThumbnailRecord: {e}")
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
                                thumb_data = extract_thumbnail_data_from_element(
                                    thumb_elem,
                                    url,
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
                            except Exception as e:
                                logger.error(f"Error processing thumbnail element: {e}")

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

    async def discover_and_scrape_thumbnails(self) -> List[ThumbnailRecord]:
        """Public method delegating to discovery orchestrator."""
        return await self.discovery_orchestrator.discover_and_scrape_thumbnails()

    async def discover_listing_urls(self) -> List[str]:
        """Public method delegating to discovery orchestrator."""
        return await self.discovery_orchestrator.discover_listing_urls()

    async def scrape_thumbnails_with_retry(
        self, listing_urls: List[str]
    ) -> List[ThumbnailRecord]:
        """Public method delegating to discovery orchestrator."""
        return await self.discovery_orchestrator.scrape_thumbnails_with_retry(
            listing_urls
        )

    async def scrape_thumbnails(self, listing_urls: List[str]) -> List[ThumbnailRecord]:
        """
        Scrape thumbnail data from listing pages (legacy method without retry).

        Args:
            listing_urls: List of listing page URLs

        Returns:
            List of ThumbnailRecord objects
        """
        # Delegate to the retry version for consistency
        return await self.scrape_thumbnails_with_retry(listing_urls)

    async def _original_scrape_articles(
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
                            "language": self.language,
                        }

                        # Apply cleaning functions to article data if configured
                        cleaning_config = self.config.cleaning
                        if cleaning_config:
                            article_data = apply_cleaning(
                                article_data, cleaning_config, self.base_url
                            )

                        article = ArticleRecord(**article_data)

                        # Stream write to CSV instead of accumulating in memory
                        self._storage.append_article(article, self.country, self.name)
                        articles_scraped += 1

                    except Exception as e:
                        logger.error(f"Failed to scrape article {thumbnail.url}: {e}")
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

    async def scrape_articles(
        self, thumbnails: List[ThumbnailRecord]
    ) -> Dict[str, Any]:
        """Public method delegating to extraction orchestrator."""
        return await self.extraction_orchestrator.scrape_articles(thumbnails)

    async def run_full_scrape(self) -> Dict[str, Any]:
        """
        Run a complete scraping operation with streaming CSV writes.

        Articles are written to CSV as they are scraped, not accumulated in memory.

        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting full scrape for {self.name} ({self.country})")

        try:
            # Initialize CSV file with headers before scraping
            csv_path = self._storage.initialize_csv(self.country, self.name)
            self._saved_files["articles"] = csv_path
            logger.info(f"Initialized CSV file for streaming writes: {csv_path}")

            # Step 1 & 2 Combined: Discover and scrape thumbnails in one pass
            # This ensures each URL is only requested once
            thumbnails = await self.discover_and_scrape_thumbnails()

            # Apply max_articles limit if set
            if self.max_articles is not None and len(thumbnails) > self.max_articles:
                logger.info(
                    f"Truncating thumbnails from {len(thumbnails)} to {self.max_articles} based on max_articles config"
                )
                thumbnails = thumbnails[: self.max_articles]

            # Step 3: Build articles with streaming CSV writes
            articles_stats = {}
            if self.prefetched_articles:
                logger.info(
                    f"Using {len(self.prefetched_articles)} prefetched articles from API JSON; skipping HTML article scraping"
                )
                # Stream write prefetched articles to CSV
                for article in self.prefetched_articles:
                    self._storage.append_article(article, self.country, self.name)
                articles_stats = {
                    "articles_scraped": len(self.prefetched_articles),
                    "articles_failed": 0,
                    "total_attempted": len(self.prefetched_articles),
                }
            else:
                # Scrape articles with streaming writes
                articles_stats = await self.scrape_articles(thumbnails)

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

        This mode discovers thumbnails batch by batch and stops when an entire batch
        of thumbnails is already in the existing articles. Only new articles are scraped.

        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting update scrape for {self.name} ({self.country})")

        try:
            # Step 1: Load existing articles to get URLs we should skip
            existing_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            logger.info(f"Found {len(existing_urls)} existing articles")

            # Reset prefetched articles for this run
            self.prefetched_articles = []

            # Step 2: Discover thumbnails batch by batch, stopping when all are already scraped
            client = self._get_http_client()
            thumbnail_selector = self.thumbnail_selectors.container
            all_thumbnails: List[ThumbnailRecord] = []
            new_thumbnails: List[ThumbnailRecord] = []
            skipped_count = 0
            stop_discovery = False

            # Get the record filter function if it's configured
            record_filter_func_name = self.config.cleaning.get("record_filter")
            record_filter_func = (
                get_cleaning_func(record_filter_func_name)
                if record_filter_func_name
                else None
            )

            async for result_batch in self.listing_strategy.discover_and_scrape(
                client, self.base_url, thumbnail_selector
            ):
                batch_thumbnails: List[ThumbnailRecord] = []
                batch_new_count = 0

                # Handle API strategy's direct return of dicts
                if isinstance(self.listing_strategy, ApiStrategy):
                    for thumb_data in result_batch:
                        try:
                            # Apply record filter if it exists
                            if record_filter_func and not record_filter_func(
                                thumb_data
                            ):
                                continue

                            # Handle URL construction from API data
                            if thumb_data.get("url"):
                                thumb_data["url"] = clean_url(
                                    thumb_data["url"], self.base_url
                                )
                            elif "url" not in thumb_data or not thumb_data["url"]:
                                url_template = self.config.listing.get(
                                    "url_construction_template"
                                )
                                if url_template:
                                    thumb_data["url"] = url_template.format(
                                        **thumb_data
                                    )

                            # Optionally build ArticleRecord directly from API data if 'body' exists
                            if thumb_data.get("body"):
                                article_dict = {
                                    "url": thumb_data["url"],
                                    "title": thumb_data.get("title", ""),
                                    "date": thumb_data.get("date", ""),
                                    "body": thumb_data.get("body", ""),
                                    "tags": thumb_data.get("tags", []),
                                    "source": self.name,
                                    "country": self.country,
                                    "language": self.language,
                                }
                                cleaning_config = self.config.cleaning or {}
                                if cleaning_config:
                                    article_dict = apply_cleaning(
                                        article_dict, cleaning_config, self.base_url
                                    )
                                try:
                                    article = ArticleRecord(**article_dict)
                                    self.prefetched_articles.append(article)
                                except Exception as e:
                                    logger.error(
                                        f"Failed to create ArticleRecord from API data: {e}"
                                    )

                            thumbnail = ThumbnailRecord(**thumb_data)
                            batch_thumbnails.append(thumbnail)

                            # Check if this thumbnail is new
                            if str(thumbnail.url) not in existing_urls:
                                batch_new_count += 1

                        except Exception as e:
                            logger.error(
                                f"Failed to create ThumbnailRecord from API data: {e}"
                            )
                    logger.info(f"Processed API batch: {len(result_batch)} thumbnails")

                else:
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
                            logger.warning(f"No thumbnails found on {result.url}")
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
                                    batch_thumbnails.append(thumbnail)

                                    # Check if this thumbnail is new
                                    if str(thumbnail.url) not in existing_urls:
                                        batch_new_count += 1

                                except Exception as e:
                                    logger.error(
                                        f"Failed to create ThumbnailRecord: {e}"
                                    )

                    logger.info(
                        f"Processed batch: {len(result_batch)} pages, {len(batch_thumbnails)} thumbnails"
                    )

                # Add batch thumbnails to totals
                for thumb in batch_thumbnails:
                    all_thumbnails.append(thumb)
                    thumb_url = str(thumb.url)
                    if thumb_url not in existing_urls:
                        new_thumbnails.append(thumb)
                    else:
                        skipped_count += 1

                # Check if entire batch is already scraped - stop discovery
                if batch_thumbnails and batch_new_count == 0:
                    logger.info(
                        f"Entire batch of {len(batch_thumbnails)} thumbnails already scraped. Stopping discovery."
                    )
                    stop_discovery = True
                    break

                logger.info(
                    f"Batch: {batch_new_count} new, {len(batch_thumbnails) - batch_new_count} existing. "
                    f"Total: {len(new_thumbnails)} new thumbnails so far."
                )

            if not stop_discovery:
                logger.info(
                    f"Discovery complete. Total: {len(all_thumbnails)} thumbnails"
                )

            logger.info(
                f"Filtered thumbnails: {len(new_thumbnails)} new, {skipped_count} already exist"
            )

            # Save thumbnails (all discovered thumbnails, not just new ones)
            saved_path = self._storage.save_thumbnails_as_urls(
                all_thumbnails, self.country, self.name
            )
            if saved_path:
                self._saved_files["urls"] = saved_path

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(new_thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating new thumbnails from {len(new_thumbnails)} to {self.max_articles} based on max_articles config"
                )
                new_thumbnails = new_thumbnails[: self.max_articles]

            # Step 3: Stream new articles directly to CSV
            new_articles_count = 0
            new_articles_failed = 0

            # Filter prefetched articles to only include new ones
            new_prefetched_articles: List[ArticleRecord] = []
            prefetched_by_url = {
                str(article.url): article for article in self.prefetched_articles
            }
            for thumb in new_thumbnails:
                thumb_url = str(thumb.url)
                if thumb_url in prefetched_by_url:
                    new_prefetched_articles.append(prefetched_by_url[thumb_url])

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
                for thumb in new_thumbnails
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

            # Mark articles file as saved (already streamed)
            csv_path = (
                self._storage.get_newspaper_dir(self.country, self.name) / "news.csv"
            )
            if csv_path.exists():
                self._saved_files["articles"] = csv_path

            # Compile results
            try:
                logger.info("Creating update results dictionary...")

                # Serialize thumbnails for metadata
                serialized_thumbnails = []
                for i, thumb in enumerate(all_thumbnails):
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
                        "thumbnails_found": len(all_thumbnails),
                        "existing_articles_skipped": skipped_count,
                        "articles_scraped": new_articles_count,
                        "articles_failed": new_articles_failed,
                        "total_articles_after_update": len(existing_urls)
                        + new_articles_count,
                        "failed_urls": len(self.failed_urls),
                        "failed_news": len(self.failed_news),
                    },
                    "data": {
                        "thumbnails": serialized_thumbnails,
                        "new_articles": "(streamed to CSV)",
                    },
                    "errors": serialized_errors,
                }

                logger.info("Update results dictionary created successfully")

            except Exception as e:
                logger.error(f"Failed to create update results dictionary: {e}")
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

    async def run_urls_only(self) -> Dict[str, Any]:
        """
        Run URL discovery only, without scraping article content.

        This mode discovers all article URLs and saves them to urls.csv,
        but does not proceed to scrape the actual article content.

        Returns:
            Dictionary with discovery results and statistics
        """
        logger.info(f"Starting URL-only discovery for {self.name} ({self.country})")

        try:
            # Discover and scrape thumbnails (URLs)
            thumbnails = await self.discover_and_scrape_thumbnails()

            # Apply max_articles limit if set
            if self.max_articles is not None and len(thumbnails) > self.max_articles:
                logger.info(
                    f"Truncating thumbnails from {len(thumbnails)} to {self.max_articles} based on max_articles config"
                )
                thumbnails = thumbnails[: self.max_articles]

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
                    "mode": "urls_only",
                    "statistics": {
                        "thumbnails_found": len(thumbnails),
                        "articles_scraped": 0,
                        "articles_failed": 0,
                        "failed_urls": len(self.failed_urls),
                    },
                    "data": {
                        "thumbnails": serialized_thumbnails,
                        "articles": "(not scraped - urls_only mode)",
                    },
                    "errors": serialized_errors,
                }

                logger.info("Results dictionary created successfully")

            except Exception as e:
                logger.error(f"Failed to create results dictionary: {e}")
                raise

            # Save failed URLs if any
            if self.failed_urls:
                saved_path = self._storage.save_failed_urls(
                    self.failed_urls, self.country, self.name
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            # Save metadata
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.name, metadata_type="urls_only"
                )
                if saved_path:
                    self._saved_files["metadata"] = saved_path
            except Exception as e:
                logger.error(f"Failed to save metadata: {e}")
                raise

            logger.info(
                f"URL-only discovery completed for {self.name}: {len(thumbnails)} URLs found"
            )
            return results

        except Exception as e:
            logger.error(f"URL-only discovery failed for {self.name}: {e}")
            error_results = {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "urls_only",
                "error": str(e),
                "statistics": {
                    "thumbnails_found": len(self.scraped_thumbnails),
                    "articles_scraped": 0,
                    "failed_urls": len(self.failed_urls),
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

    async def _discover_thumbnails_incremental(
        self,
        existing_urls: set,
        check_existing: bool = True,
    ) -> List[ThumbnailRecord]:
        """
        Discover thumbnails with all stopping rules.

        Args:
            existing_urls: Set of URLs already in urls.csv
            check_existing: If True, stop when batch is in existing_urls (Rule 4)

        Returns:
            List of newly discovered ThumbnailRecord objects
        """
        client = self._get_http_client()
        thumbnail_selector = self.thumbnail_selectors.container
        all_thumbnails: List[ThumbnailRecord] = []
        previous_batch_data = None

        # Get the record filter function if it's configured
        record_filter_func_name = self.config.cleaning.get("record_filter")
        record_filter_func = (
            get_cleaning_func(record_filter_func_name)
            if record_filter_func_name
            else None
        )

        async for result_batch in self.listing_strategy.discover_and_scrape(
            client, self.base_url, thumbnail_selector
        ):
            batch_thumbnails: List[ThumbnailRecord] = []

            # Handle API strategy's direct return of dicts
            if isinstance(self.listing_strategy, ApiStrategy):
                for thumb_data in result_batch:
                    try:
                        # Apply record filter if it exists
                        if record_filter_func and not record_filter_func(thumb_data):
                            continue

                        # Handle URL construction from API data
                        if thumb_data.get("url"):
                            thumb_data["url"] = clean_url(
                                thumb_data["url"], self.base_url
                            )
                        elif "url" not in thumb_data or not thumb_data["url"]:
                            url_template = self.config.listing.get(
                                "url_construction_template"
                            )
                            if url_template:
                                thumb_data["url"] = url_template.format(**thumb_data)

                        # Optionally build ArticleRecord directly from API data if 'body' exists
                        if thumb_data.get("body"):
                            article_dict = {
                                "url": thumb_data["url"],
                                "title": thumb_data.get("title", ""),
                                "date": thumb_data.get("date", ""),
                                "body": thumb_data.get("body", ""),
                                "tags": thumb_data.get("tags", []),
                                "source": self.name,
                                "country": self.country,
                                "language": self.language,
                            }
                            cleaning_config = self.config.cleaning or {}
                            if cleaning_config:
                                article_dict = apply_cleaning(
                                    article_dict, cleaning_config, self.base_url
                                )
                            try:
                                article = ArticleRecord(**article_dict)
                                self.prefetched_articles.append(article)
                            except Exception as e:
                                logger.error(
                                    f"Failed to create ArticleRecord from API data: {e}"
                                )

                        thumbnail = ThumbnailRecord(**thumb_data)
                        batch_thumbnails.append(thumbnail)

                    except Exception as e:
                        logger.error(
                            f"Failed to create ThumbnailRecord from API data: {e}"
                        )
                logger.info(f"Processed API batch: {len(result_batch)} items")

            else:
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
                                batch_thumbnails.append(thumbnail)
                            except Exception as e:
                                logger.error(f"Failed to create ThumbnailRecord: {e}")

                logger.info(
                    f"Processed batch: {len(result_batch)} pages, {len(batch_thumbnails)} thumbnails"
                )

            # Rule 1: 404/error - handled by listing_strategy (no successful results)
            # Rule 2: Empty thumbnails batch
            if not batch_thumbnails:
                logger.info("Empty batch. Stopping discovery.")
                break

            # Rule 3: Identical batch data
            batch_data = [thumb.model_dump() for thumb in batch_thumbnails]
            if previous_batch_data is not None and batch_data == previous_batch_data:
                logger.info("Identical batch data. Stopping discovery.")
                break

            # Rule 4: Batch already in urls.csv (only if check_existing=True)
            if check_existing and existing_urls:
                batch_urls = {str(thumb.url) for thumb in batch_thumbnails}
                if batch_urls.issubset(existing_urls):
                    logger.info("Batch already in urls.csv. Stopping discovery.")
                    break

            # Add to results
            all_thumbnails.extend(batch_thumbnails)
            previous_batch_data = batch_data

        logger.info(f"Total thumbnails discovered: {len(all_thumbnails)}")
        return all_thumbnails

    async def run_discover(self) -> Dict[str, Any]:
        """
        Incremental URL discovery mode.

        Behavior:
        1. Ensure urls.csv exists (create from news.csv if needed)
        2. Load existing URLs from urls.csv
        3. Discover thumbnails batch-by-batch
        4. Apply stopping rules (404, empty, identical, batch in urls.csv)
        5. Append new URLs to urls.csv (deduplicated)
        6. NO article scraping

        Returns:
            Dictionary with discovery results and statistics
        """
        logger.info(f"Starting DISCOVER mode for {self.name} ({self.country})")

        try:
            # Step 1: Ensure urls.csv exists
            created = self._storage.ensure_urls_csv_from_news(self.country, self.name)
            if created:
                logger.info("Created urls.csv from existing news.csv")

            # Step 2: Load existing URLs from urls.csv
            existing_urls = self._storage.get_existing_urls(self.country, self.name)
            logger.info(f"Loaded {len(existing_urls)} existing URLs from urls.csv")

            # Reset prefetched articles
            self.prefetched_articles = []

            # Step 3 & 4: Discover thumbnails with stopping rules
            new_thumbnails = await self._discover_thumbnails_incremental(
                existing_urls=existing_urls,
                check_existing=True,  # Apply Rule 4
            )

            # Step 5: Append new URLs to urls.csv (deduplicated)
            if new_thumbnails:
                saved_path = self._storage.append_thumbnails_to_urls(
                    new_thumbnails, self.country, self.name
                )
                if saved_path:
                    self._saved_files["urls"] = saved_path
                logger.info(f"Appended {len(new_thumbnails)} new URLs to urls.csv")
            else:
                logger.info("No new URLs discovered")

            # Compile results
            results = {
                "success": True,
                "newspaper": self.name,
                "country": self.country,
                "mode": "discover",
                "statistics": {
                    "existing_urls": len(existing_urls),
                    "new_urls_discovered": len(new_thumbnails),
                    "total_urls_after": len(existing_urls) + len(new_thumbnails),
                    "articles_scraped": 0,
                    "failed_urls": len(self.failed_urls),
                },
            }

            # Save metadata
            self._storage.save_metadata(
                results, self.country, self.name, metadata_type="discover"
            )

            logger.info(
                f"DISCOVER mode completed: {len(new_thumbnails)} new URLs found"
            )
            return results

        except Exception as e:
            logger.error(f"DISCOVER mode failed for {self.name}: {e}")
            return {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "discover",
                "error": str(e),
            }

    async def run_discover_full(self) -> Dict[str, Any]:
        """
        Full URL discovery mode.

        Behavior:
        1. Discover ALL thumbnails (no urls.csv stopping rule)
        2. Apply stopping rules (404, empty, identical) - NOT Rule 4
        3. OVERWRITE urls.csv with all discovered URLs
        4. NO article scraping

        Returns:
            Dictionary with discovery results and statistics
        """
        logger.info(f"Starting DISCOVER-FULL mode for {self.name} ({self.country})")

        try:
            # Reset prefetched articles
            self.prefetched_articles = []

            # Discover ALL thumbnails (no Rule 4 - don't check existing)
            all_thumbnails = await self._discover_thumbnails_incremental(
                existing_urls=set(),  # Empty set - don't check
                check_existing=False,  # Disable Rule 4
            )

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(all_thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating thumbnails from {len(all_thumbnails)} to {self.max_articles}"
                )
                all_thumbnails = all_thumbnails[: self.max_articles]

            # OVERWRITE urls.csv with all discovered URLs
            if all_thumbnails:
                saved_path = self._storage.save_thumbnails_as_urls(
                    all_thumbnails, self.country, self.name
                )
                if saved_path:
                    self._saved_files["urls"] = saved_path
                logger.info(f"Saved {len(all_thumbnails)} URLs to urls.csv (overwrite)")
            else:
                logger.warning("No URLs discovered")

            # Compile results
            results = {
                "success": True,
                "newspaper": self.name,
                "country": self.country,
                "mode": "discover_full",
                "statistics": {
                    "urls_discovered": len(all_thumbnails),
                    "articles_scraped": 0,
                    "failed_urls": len(self.failed_urls),
                },
            }

            # Save metadata
            self._storage.save_metadata(
                results, self.country, self.name, metadata_type="discover_full"
            )

            logger.info(
                f"DISCOVER-FULL mode completed: {len(all_thumbnails)} URLs found"
            )
            return results

        except Exception as e:
            logger.error(f"DISCOVER-FULL mode failed for {self.name}: {e}")
            return {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "discover_full",
                "error": str(e),
            }

    async def run_resume(self) -> Dict[str, Any]:
        """
        Resume article scraping mode.

        Behavior:
        1. Ensure urls.csv exists (create from news.csv if needed)
        2. Load URLs from urls.csv
        3. Load existing article URLs from news.csv
        4. Identify pending articles: urls.csv - news.csv
        5. Scrape pending articles
        6. Append to news.csv
        7. NO discovery

        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting RESUME mode for {self.name} ({self.country})")

        try:
            # Step 1: Ensure urls.csv exists
            created = self._storage.ensure_urls_csv_from_news(self.country, self.name)
            if created:
                logger.info("Created urls.csv from existing news.csv")

            # Step 2: Load URLs from urls.csv
            thumbnails = self._storage.load_urls_from_csv(self.country, self.name)
            if thumbnails is None:
                logger.warning("No urls.csv found. Nothing to resume.")
                return {
                    "success": True,
                    "newspaper": self.name,
                    "country": self.country,
                    "mode": "resume",
                    "statistics": {
                        "urls_in_csv": 0,
                        "existing_articles": 0,
                        "pending_articles": 0,
                        "articles_scraped": 0,
                    },
                }

            logger.info(f"Loaded {len(thumbnails)} URLs from urls.csv")

            # Step 3: Load existing article URLs from news.csv
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            logger.info(
                f"Found {len(existing_article_urls)} existing articles in news.csv"
            )

            # Step 4: Identify pending articles
            pending_thumbnails = [
                thumb
                for thumb in thumbnails
                if str(thumb.url) not in existing_article_urls
            ]
            logger.info(f"Pending articles to scrape: {len(pending_thumbnails)}")

            if not pending_thumbnails:
                logger.info("No pending articles to scrape")
                return {
                    "success": True,
                    "newspaper": self.name,
                    "country": self.country,
                    "mode": "resume",
                    "statistics": {
                        "urls_in_csv": len(thumbnails),
                        "existing_articles": len(existing_article_urls),
                        "pending_articles": 0,
                        "articles_scraped": 0,
                    },
                }

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(pending_thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating pending from {len(pending_thumbnails)} to {self.max_articles}"
                )
                pending_thumbnails = pending_thumbnails[: self.max_articles]

            # Step 5 & 6: Scrape pending articles (appends to news.csv)
            scrape_stats = await self.scrape_articles(pending_thumbnails)

            # Mark articles file as saved
            csv_path = (
                self._storage.get_newspaper_dir(self.country, self.name) / "news.csv"
            )
            if csv_path.exists():
                self._saved_files["articles"] = csv_path

            # Compile results
            results = {
                "success": True,
                "newspaper": self.name,
                "country": self.country,
                "mode": "resume",
                "statistics": {
                    "urls_in_csv": len(thumbnails),
                    "existing_articles": len(existing_article_urls),
                    "pending_articles": len(pending_thumbnails),
                    "articles_scraped": scrape_stats.get("articles_scraped", 0),
                    "articles_failed": scrape_stats.get("articles_failed", 0),
                    "failed_news": len(self.failed_news),
                },
            }

            # Save failed news if any
            if self.failed_news:
                self._storage.save_failed_news(
                    self.failed_news, self.country, self.name
                )

            # Save metadata
            self._storage.save_metadata(
                results, self.country, self.name, metadata_type="resume"
            )

            logger.info(
                f"RESUME mode completed: {scrape_stats.get('articles_scraped', 0)} articles scraped"
            )
            return results

        except Exception as e:
            logger.error(f"RESUME mode failed for {self.name}: {e}")
            return {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "resume",
                "error": str(e),
            }

    async def run_default(self) -> Dict[str, Any]:
        """
        Default smart update mode.

        Behavior:
        1. Ensure urls.csv exists (create from news.csv if needed)
        2. Load existing URLs from urls.csv
        3. Discover thumbnails batch-by-batch with stopping rules
        4. Append new URLs to urls.csv (deduplicated)
        5. Load existing article URLs from news.csv
        6. Identify pending articles: urls.csv - news.csv
        7. Scrape pending articles
        8. Append to news.csv

        Returns:
            Dictionary with discovery and scraping results
        """
        logger.info(f"Starting DEFAULT mode for {self.name} ({self.country})")

        try:
            # Step 1: Ensure urls.csv exists
            created = self._storage.ensure_urls_csv_from_news(self.country, self.name)
            if created:
                logger.info("Created urls.csv from existing news.csv")

            # Step 2: Load existing URLs from urls.csv
            existing_urls = self._storage.get_existing_urls(self.country, self.name)
            logger.info(f"Loaded {len(existing_urls)} existing URLs from urls.csv")

            # Reset prefetched articles
            self.prefetched_articles = []

            # Step 3: Discover thumbnails with stopping rules
            new_thumbnails = await self._discover_thumbnails_incremental(
                existing_urls=existing_urls,
                check_existing=True,  # Apply Rule 4
            )

            # Step 4: Append new URLs to urls.csv (deduplicated)
            if new_thumbnails:
                saved_path = self._storage.append_thumbnails_to_urls(
                    new_thumbnails, self.country, self.name
                )
                if saved_path:
                    self._saved_files["urls"] = saved_path
                logger.info(f"Appended {len(new_thumbnails)} new URLs to urls.csv")

            # Step 5: Load existing article URLs from news.csv
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.name
            )
            logger.info(f"Found {len(existing_article_urls)} existing articles")

            # Step 6: Identify pending articles (all urls.csv - news.csv)
            # Reload urls.csv to get complete list including newly added
            all_thumbnails = self._storage.load_urls_from_csv(self.country, self.name)
            if all_thumbnails is None:
                all_thumbnails = []

            pending_thumbnails = [
                thumb
                for thumb in all_thumbnails
                if str(thumb.url) not in existing_article_urls
            ]
            logger.info(f"Pending articles to scrape: {len(pending_thumbnails)}")

            # Handle prefetched articles from API
            articles_from_api = 0
            if self.prefetched_articles:
                # Filter to only new prefetched articles
                new_prefetched = [
                    article
                    for article in self.prefetched_articles
                    if str(article.url) not in existing_article_urls
                ]
                if new_prefetched:
                    logger.info(
                        f"Writing {len(new_prefetched)} prefetched articles from API"
                    )
                    for article in new_prefetched:
                        self._storage.append_article(article, self.country, self.name)
                        articles_from_api += 1

                # Remove prefetched URLs from pending
                prefetched_urls = {str(a.url) for a in self.prefetched_articles}
                pending_thumbnails = [
                    t for t in pending_thumbnails if str(t.url) not in prefetched_urls
                ]

            # Apply max_articles limit if set
            if (
                self.max_articles is not None
                and len(pending_thumbnails) > self.max_articles
            ):
                logger.info(
                    f"Truncating pending from {len(pending_thumbnails)} to {self.max_articles}"
                )
                pending_thumbnails = pending_thumbnails[: self.max_articles]

            # Step 7 & 8: Scrape pending articles
            scrape_stats = {"articles_scraped": 0, "articles_failed": 0}
            if pending_thumbnails:
                scrape_stats = await self.scrape_articles(pending_thumbnails)

            total_scraped = scrape_stats.get("articles_scraped", 0) + articles_from_api

            # Mark articles file as saved
            csv_path = (
                self._storage.get_newspaper_dir(self.country, self.name) / "news.csv"
            )
            if csv_path.exists():
                self._saved_files["articles"] = csv_path

            # Compile results
            results = {
                "success": True,
                "newspaper": self.name,
                "country": self.country,
                "mode": "default",
                "statistics": {
                    "existing_urls": len(existing_urls),
                    "new_urls_discovered": len(new_thumbnails),
                    "existing_articles": len(existing_article_urls),
                    "articles_scraped": total_scraped,
                    "articles_failed": scrape_stats.get("articles_failed", 0),
                    "failed_urls": len(self.failed_urls),
                    "failed_news": len(self.failed_news),
                },
            }

            # Save failed URLs and news if any
            if self.failed_urls:
                self._storage.save_failed_urls(
                    self.failed_urls, self.country, self.name
                )
            if self.failed_news:
                self._storage.save_failed_news(
                    self.failed_news, self.country, self.name
                )

            # Save metadata
            self._storage.save_metadata(
                results, self.country, self.name, metadata_type="default"
            )

            logger.info(
                f"DEFAULT mode completed: {len(new_thumbnails)} new URLs, "
                f"{total_scraped} articles scraped"
            )
            return results

        except Exception as e:
            logger.error(f"DEFAULT mode failed for {self.name}: {e}")
            return {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "default",
                "error": str(e),
            }
