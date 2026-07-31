"""
Slim newspaper scraper orchestrator.

This module provides the main NewspaperScraper class that orchestrates
discovery and extraction operations through specialized orchestrators.

This is Phase 1 of the refactoring - the orchestrators delegate back to
the original methods for now. Full migration will happen in Phase 2.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Callable, List, Dict, Optional, Any, TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .observability import ProgressReporter
import httpx
from .client_http import AsyncHttpClient
from .client_browser import BrowserClient
from .strategies import (
    create_listing_strategy,
    ApiStrategy,
    ArchiveStrategy,
    PaginatedArchiveStrategy,
)
from .models import (
    ThumbnailRecord,
    ArticleRecord,
    NewspaperConfig,
)
from .pipelines.cleaning import apply_cleaning
from .pipelines.storage import CSVStorage
from .parser import (
    extract_thumbnail_data_from_element,
    extract_article_data_from_soup,
)
from .discovery import DiscoveryOrchestrator
from .extraction import ExtractionOrchestrator
from .observability import ScraperMetrics
from .filters import compile_listing_filters

logger = logging.getLogger(__name__)

# Number of article scraping attempts after which the early-abort gate fires
# if articles_scraped is still 0. Indicates likely-broken selectors.
EARLY_ABORT_THRESHOLD = 5

# Per-batch watchdog timeout for asyncio.gather of article-fetch tasks.
# When a server blackholes the client (TCP-level stall, no FIN/RST), httpx's
# per-request timeout can fail to interrupt promptly and all concurrency slots
# pile up. The watchdog cancels the whole batch after this many seconds and
# the URLs are recorded as cancelled-by-watchdog so they remain unattempted
# from the failure-ledger's POV (next run picks them up automatically).
BATCH_TIMEOUT_SECONDS = 90


class EarlyAbortError(RuntimeError):
    """Raised when the early-abort gate fires inside _original_scrape_articles.

    Subclass of RuntimeError so it satisfies the spec, but distinct enough that
    the run_* methods can re-raise it without being swallowed by their broad
    `except Exception` handlers (which return an error dict for ordinary
    failures). The exception must propagate all the way to collect.py's
    per-source handler so the source is marked failed and the next source
    in the plan continues processing.
    """

    pass


class NewspaperScraper:
    """
    Generic newspaper scraper driven by configuration.

    This class can scrape any newspaper based on a configuration
    dictionary that specifies selectors, listing strategy, and
    other site-specific parameters.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        progress_reporter: Optional["ProgressReporter"] = None,
    ):
        """
        Initialize the newspaper scraper with configuration.

        Args:
            config: Configuration dictionary (validated against NewspaperConfig)
        """
        # Validate configuration
        self.config = NewspaperConfig(**config)

        # Basic properties
        self.name = self.config.name
        self.source_key = config.get("_source_key") or re.sub(
            r"[^\w\-_.]", "_", self.config.name.replace(" ", "_").lower()
        ).strip("_")
        self.country = self.config.country
        self.base_url = str(self.config.base_url)
        self.language = self.config.language or "en"

        # Initialize metrics tracking
        self.metrics = ScraperMetrics(
            newspaper=self.name,
            country=self.country,
            mode="update",  # Will be set by run method
            started_at=datetime.utcnow(),
        )

        # Store limits from config
        self.max_pages = self.config.max_pages
        self.max_articles = self.config.max_articles

        # When True, the failed_urls_seen.csv ledger is not subtracted from
        # the pending set — every URL not already in news.csv is attempted.
        # The ledger is still updated (failures upserted, successes evicted).
        self.retry_failed: bool = False
        # Per-run set of URLs that successfully landed in news.csv. Populated
        # by _original_scrape_articles after each append_article. Consumed by
        # run_default / run_resume to evict from the ledger.
        self._scraped_urls_this_run: set = set()
        # Per-run set of URLs whose batch hit the watchdog timeout. Excluded
        # from the failure ledger so the next run will retry them.
        self._cancelled_by_watchdog: set = set()

        # Initialize client based on configuration
        self.client_type = self.config.client
        self._http_client: Optional[AsyncHttpClient] = None
        self._browser_client: Optional[BrowserClient] = None

        # Initialize listing strategy
        self.listing_strategy = create_listing_strategy(
            self.config.listing, max_pages=self.config.max_pages
        )

        # Compile declarative listing URL filters (optional)
        self._listing_filters = compile_listing_filters(self.config.listing)
        self._filtered_url_counts: Dict[str, int] = {"discovery": 0, "pending": 0}
        self._filtered_url_samples: Dict[str, List[str]] = {
            "discovery": [],
            "pending": [],
        }
        self._filtered_url_logged: Dict[str, bool] = {
            "discovery": False,
            "pending": False,
        }

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

        # Store progress reporter (can be None for single-scraper runs)
        self.progress = progress_reporter

        # Early-abort gate prompt callback. If set, the gate calls this with
        # the attempt count instead of raising EarlyAbortError immediately;
        # callback returns True to continue scraping (suppressing further
        # checks for this run) or False to abort. If None, the gate aborts
        # unconditionally — see _original_scrape_articles. The callback is
        # invoked via asyncio.to_thread so it can use blocking input prompts
        # (e.g. click.confirm) without stalling the event loop.
        self.on_early_abort: Optional[Callable[[int], bool]] = None
        self._early_abort_acknowledged: bool = False

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

    def _track_extraction(self, data: Dict[str, Any], stage: str) -> None:
        """
        Track field-level extraction quality in metrics.

        For each field in the extracted data, records whether it was
        successfully populated or empty/missing.

        Args:
            data: Dictionary of extracted fields
            stage: Extraction stage ("thumbnail" or "article")
        """
        for field_name, value in data.items():
            # Get or create field metric
            field_metric = self.metrics.get_field_metric(field_name)
            field_metric.total_extracted += 1

            # Check if value is empty
            if value is None or value == "" or value == []:
                field_metric.empty += 1
                logger.warning(
                    f"Empty {field_name} in {stage}: {data.get('url', 'unknown')}"
                )
            else:
                field_metric.successful += 1

    def _is_url_allowed(self, url: Any, *, stage: str) -> bool:
        """Apply declarative `listing.filters` URL rules.

        Args:
            url: URL to evaluate (string or HttpUrl)
            stage: Either "discovery" or "pending" for metrics/logging

        Returns:
            True if URL passes filters or filters are not configured.
        """

        if not self._listing_filters.enabled:
            return True

        url_str = str(url) if url is not None else ""
        if not url_str:
            return True

        allowed = self._listing_filters.is_allowed(url_str)
        if allowed:
            return True

        if stage not in self._filtered_url_counts:
            stage = "discovery"

        self._filtered_url_counts[stage] += 1

        # Keep a small sample for debugging.
        samples = self._filtered_url_samples[stage]
        if len(samples) < 5:
            samples.append(url_str)

        return False

    def _log_filter_stats(self, *, stage: str) -> None:
        if not self._listing_filters.enabled:
            return
        if stage not in self._filtered_url_counts:
            return
        if self._filtered_url_logged.get(stage):
            return

        count = self._filtered_url_counts.get(stage, 0)
        if count:
            logger.info(
                f"Filtered out {count} URL(s) during {stage} using listing.filters"
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"Filtered {stage} URL sample(s) (up to 5): {self._filtered_url_samples.get(stage, [])}"
                )

        self._filtered_url_logged[stage] = True

    def _process_api_thumbnail(
        self, thumb_data: Dict[str, Any], existing_urls: Optional[set] = None
    ) -> Optional[ThumbnailRecord]:
        """
        Process a single API thumbnail: clean, validate, track metrics.

        This is the single point of truth for API thumbnail processing.
        Used by all scrape modes (UPDATE, RESUME, FULL).

        Args:
            thumb_data: Raw thumbnail data from API
            existing_urls: Set of URLs already scraped (optional)

        Returns:
            ThumbnailRecord or None if filtered/invalid
        """
        from pydantic import ValidationError
        from .pipelines.cleaning import apply_cleaning, get_cleaning_func
        from .pipelines.cleaning.common import clean_url

        # Apply record filter if configured
        record_filter_func_name = (
            self.config.cleaning.get("record_filter") if self.config.cleaning else None
        )
        if record_filter_func_name:
            record_filter_func = get_cleaning_func(record_filter_func_name)
            if record_filter_func and not record_filter_func(thumb_data):
                return None

        # Clean URL - ensure it's absolute
        if thumb_data.get("url"):
            thumb_data["url"] = clean_url(thumb_data["url"], self.base_url)
        elif "url" not in thumb_data or not thumb_data["url"]:
            # URL construction from template if needed
            url_template = self.config.listing.get("url_construction_template")
            if url_template:
                thumb_data["url"] = url_template.format(**thumb_data)

        # Apply declarative listing URL filters (after URL is constructed/normalized)
        if thumb_data.get("url") and not self._is_url_allowed(
            thumb_data["url"], stage="discovery"
        ):
            return None

        # Apply cleaning - CRITICAL STEP that was missing in UPDATE mode
        # Update in-place so callers see cleaned values (e.g. body for prefetched articles)
        cleaning_config = self.config.cleaning or {}
        if cleaning_config:
            cleaned = apply_cleaning(thumb_data, cleaning_config, self.base_url)
            thumb_data.update(cleaned)

        # Track metrics BEFORE creating record
        self._track_extraction(thumb_data, stage="thumbnail")

        # Create ThumbnailRecord
        try:
            thumbnail = ThumbnailRecord(**thumb_data)
            return thumbnail
        except ValidationError as e:
            self.metrics.articles_failed += 1
            logger.error(f"Invalid thumbnail data: {e}")
            logger.debug(f"Data: {thumb_data}")
            return None

    def _process_html_thumbnail(
        self, thumb_data: Dict[str, Any], *, stage: str = "discovery"
    ) -> Optional[ThumbnailRecord]:
        """Filter + validate a thumbnail record from HTML extraction."""

        url = thumb_data.get("url")
        if url and not self._is_url_allowed(url, stage=stage):
            return None

        try:
            return ThumbnailRecord(**thumb_data)
        except Exception as e:
            logger.error(f"Failed to create ThumbnailRecord: {e}")
            logger.debug(f"Data: {thumb_data}")
            return None

    def _maybe_prefetch_feed_body(self, thumb_elem, thumbnail) -> None:
        """
        For listing strategies that carry the body in the feed item (RSS
        body_in_feed), read the body straight from the element and register it as a
        prefetched article so the per-URL article fetch is skipped. Items without an
        in-feed body are left alone and fall back to the article page.
        """
        if not getattr(self.listing_strategy, "body_in_feed", False):
            return
        body = self.listing_strategy.extract_body(thumb_elem)
        if not body:
            return
        article_dict = {
            "url": str(thumbnail.url),
            "title": thumbnail.title,
            "date": thumbnail.date or "",
            "body": body,
            "tags": [],
            "source": self.name,
            "country": self.country,
            "language": self.language,
        }
        try:
            self.prefetched_articles.append(ArticleRecord(**article_dict))
        except Exception as e:
            logger.error(
                f"Failed to build prefetched ArticleRecord from feed body: {e}"
            )

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
        seen_urls: set[str] = set()
        thumbnail_selector = self.thumbnail_selectors.container

        async for result_batch in self.listing_strategy.discover_and_scrape(
            client, self.base_url, thumbnail_selector
        ):
            batch_new_count = 0

            # Handle API strategy's direct return of dicts
            if isinstance(self.listing_strategy, ApiStrategy):
                for thumb_data in result_batch:
                    # Use unified processing method
                    thumbnail = self._process_api_thumbnail(thumb_data)

                    if thumbnail:
                        url_str = str(thumbnail.url)
                        if url_str in seen_urls:
                            continue
                        seen_urls.add(url_str)
                        batch_new_count += 1
                        thumbnails.append(thumbnail)

                        # Handle prefetched articles
                        if thumb_data.get("body"):
                            article_dict = {
                                "url": url_str,
                                "title": thumbnail.title,
                                "date": thumbnail.date or "",
                                "body": thumb_data.get("body", ""),
                                "tags": thumb_data.get("tags", []),
                                "source": self.name,
                                "country": self.country,
                                "language": self.language,
                            }
                            try:
                                article = ArticleRecord(**article_dict)
                                self.prefetched_articles.append(article)
                            except Exception as e:
                                logger.error(
                                    f"Failed to create ArticleRecord from API data: {e}"
                                )
                                logger.debug(f"Article data: {article_dict}")

                logger.info(
                    f"Processed API batch: {len(result_batch)} items, {batch_new_count} new"
                )

                # Update progress after each API batch to keep progress file fresh
                if self.progress:
                    self.progress.update(urls_found=len(thumbnails))

                if batch_new_count == 0:
                    logger.info("All URLs in batch already seen — stopping discovery.")
                    break

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
                        thumbnail = self._process_html_thumbnail(
                            thumb_data, stage="discovery"
                        )
                        if thumbnail:
                            url_str = str(thumbnail.url)
                            if url_str in seen_urls:
                                continue
                            seen_urls.add(url_str)
                            batch_new_count += 1
                            thumbnails.append(thumbnail)
                            self._maybe_prefetch_feed_body(thumb_elem, thumbnail)

            logger.info(
                f"Processed batch: {len(result_batch)} pages, {len(thumbnails)} total thumbnails, {batch_new_count} new"
            )

            # Update progress after each batch to keep progress file fresh
            if self.progress:
                self.progress.update(urls_found=len(thumbnails))

            if batch_new_count == 0:
                if isinstance(
                    self.listing_strategy, (ArchiveStrategy, PaginatedArchiveStrategy)
                ):
                    logger.info(
                        "All URLs in batch already seen — skipping (archive strategy continues)."
                    )
                else:
                    logger.info("All URLs in batch already seen — stopping discovery.")
                    break

        logger.info(f"Total thumbnails discovered and scraped: {len(thumbnails)}")

        # Log any filter stats once per run
        self._log_filter_stats(stage="discovery")

        # Save thumbnails to JSONL file
        saved_path = self._storage.save_thumbnails_as_urls(
            thumbnails, self.country, self.source_key
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
                        thumbnail = self._process_html_thumbnail(
                            thumb_data, stage="discovery"
                        )
                        if thumbnail:
                            thumbnails.append(thumbnail)

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
                                    thumbnail = self._process_html_thumbnail(
                                        thumb_data, stage="discovery"
                                    )
                                    if thumbnail:
                                        thumbnails.append(thumbnail)
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

        # Log any filter stats once per run
        self._log_filter_stats(stage="discovery")
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

    async def _check_early_abort(self, attempts: int) -> None:
        """Run the early-abort gate logic.

        Called from both the mid-loop and end-of-loop check sites in
        `_original_scrape_articles` when `articles_scraped == 0` after at
        least one article attempt. Behavior:

        - If `_early_abort_acknowledged` is True, return immediately. The
          user has already opted to continue this run; do not re-prompt.
        - If `on_early_abort` is None, raise `EarlyAbortError` unconditionally
          (the original fail-fast behavior with no callback registered).
        - Otherwise, invoke the callback in a worker thread (so blocking
          prompts like `click.confirm` don't stall the asyncio event loop).
          If the callback returns True, set `_early_abort_acknowledged` so
          subsequent gate checks in this run are no-ops. If it returns False,
          raise `EarlyAbortError`.

        Args:
            attempts: Number of article attempts that have been made when the
                gate fired. Used in the error/prompt message and passed to
                the callback.
        """
        if self._early_abort_acknowledged:
            return

        message = (
            f"Early validation shows that selectors could be broken: "
            f"after {attempts} attempts of scraping articles, "
            f"0 were actually scraped!"
        )

        if self.on_early_abort is None:
            raise EarlyAbortError(message)

        should_continue = await asyncio.to_thread(self.on_early_abort, attempts)
        if should_continue:
            self._early_abort_acknowledged = True
            logger.info(
                "Early-abort gate fired at %d attempts; user opted to continue. "
                "Suppressing further early-abort checks for this run.",
                attempts,
            )
            return

        raise EarlyAbortError(message)

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
        # Apply listing.filters to pending scrape as well (urls.csv can contain legacy junk)
        filtered_listing = 0
        if self._listing_filters.enabled and thumbnails:
            before = len(thumbnails)
            thumbnails = [
                t for t in thumbnails if self._is_url_allowed(t.url, stage="pending")
            ]
            filtered_listing = before - len(thumbnails)
            if filtered_listing:
                logger.info(
                    f"Skipping {filtered_listing} pending URL(s) due to listing.filters"
                )
            self._log_filter_stats(stage="pending")

        # Also count discovery-phase filtered URLs
        filtered_listing += self._filtered_url_counts.get("discovery", 0)

        article_urls = [str(thumb.url) for thumb in thumbnails]
        articles_scraped = 0
        failed_http = 0
        failed_body = 0
        failed_date = 0
        warning_title = 0
        warning_tags = 0
        # Reset per-run success set so the run_* methods can evict succeeded
        # URLs from the failure ledger after this method returns.
        self._scraped_urls_this_run = set()
        self._cancelled_by_watchdog = set()

        # Reset per-run early-abort state. The acknowledgement flag is on the
        # instance so the helper method can read it, but it MUST NOT carry
        # across multiple invocations of the same scraper instance.
        self._early_abort_acknowledged = False

        if self.client_type == "http":
            client = self._get_http_client()

            from tqdm.asyncio import tqdm

            logger.info(f"Scraping {len(article_urls)} articles...")

            # Batched parallel article fetch. The semaphore in
            # AsyncHttpClient.request_url enforces the actual concurrency cap;
            # gathering `batch_size` tasks just feeds the semaphore. Per-item
            # processing (parse, validate, ledger write) stays serial because
            # it mutates shared state (storage, counters, early-abort).
            batch_size = max(1, self.config.concurrency or 10)

            async with httpx.AsyncClient() as http_client:
                progress_bar = tqdm(total=len(thumbnails), desc="Scraping articles")
                try:
                    i = -1
                    for batch_start in range(0, len(thumbnails), batch_size):
                        batch = thumbnails[batch_start : batch_start + batch_size]
                        fetch_tasks = [
                            client.request_url(http_client, str(t.url)) for t in batch
                        ]
                        try:
                            batch_results = await asyncio.wait_for(
                                asyncio.gather(*fetch_tasks, return_exceptions=True),
                                timeout=BATCH_TIMEOUT_SECONDS,
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"Batch watchdog fired after {BATCH_TIMEOUT_SECONDS}s "
                                f"(batch_start={batch_start}, size={len(batch)}); "
                                f"cancelling and continuing"
                            )
                            self._cancelled_by_watchdog.update(
                                str(t.url) for t in batch
                            )
                            failed_http += len(batch)
                            for _ in batch:
                                i += 1
                                progress_bar.update(1)
                            continue

                        for thumbnail, result in zip(batch, batch_results):
                            i += 1
                            progress_bar.update(1)

                            # Early-abort gate: if EARLY_ABORT_THRESHOLD attempts have
                            # already completed and none of them passed validation,
                            # invoke the gate. Behavior depends on whether an
                            # on_early_abort callback is registered — see
                            # _check_early_abort. Checked at the top of each iteration
                            # because the validation `continue` paths below would
                            # skip a check placed at the end of the loop body.
                            if i >= EARLY_ABORT_THRESHOLD and articles_scraped == 0:
                                await self._check_early_abort(EARLY_ABORT_THRESHOLD)

                            if isinstance(result, BaseException):
                                logger.error(
                                    f"Failed to scrape article {thumbnail.url}: {result}"
                                )
                                failed_http += 1
                                continue

                            content, status_code = result

                            try:
                                if content is None:
                                    self._add_failed_news(
                                        url=thumbnail.url,
                                        status_code=status_code,
                                        error="Failed to retrieve content",
                                        stage="article_content",
                                    )
                                    failed_http += 1
                                    if self.progress and (i + 1) % 10 == 0:
                                        self.progress.update(
                                            articles_scraped=articles_scraped,
                                            articles_failed=failed_http
                                            + failed_body
                                            + failed_date,
                                        )
                                    continue

                                soup = client.parse_content(content)

                                article_content = extract_article_data_from_soup(
                                    soup,
                                    str(thumbnail.url),
                                    self.article_selectors,
                                    self.base_url,
                                    self.config.cleaning,
                                )

                                # Prefer the article-page title when available. This
                                # matters for sitemap-based configs where thumbnail.title
                                # is a URL placeholder (loc::text).
                                article_title = (
                                    article_content.get("title") or thumbnail.title
                                )
                                article_data = {
                                    "url": str(thumbnail.url),
                                    "title": article_title,
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

                                cleaning_config = self.config.cleaning
                                if cleaning_config:
                                    article_data = apply_cleaning(
                                        article_data, cleaning_config, self.base_url
                                    )

                                # Validate required fields — skip articles with empty body or date
                                body_val = (article_data.get("body") or "").strip()
                                date_val = (article_data.get("date") or "").strip()

                                if not body_val:
                                    failed_body += 1
                                    logger.debug(
                                        f"Skipping article (empty body): {thumbnail.url}"
                                    )
                                    continue

                                if not date_val:
                                    failed_date += 1
                                    logger.debug(
                                        f"Skipping article (empty date): {thumbnail.url}"
                                    )
                                    continue

                                # Track warnings for non-critical empty fields
                                title_val = (article_data.get("title") or "").strip()
                                tags_val = article_data.get("tags")
                                if not title_val:
                                    warning_title += 1
                                if not tags_val or tags_val == []:
                                    warning_tags += 1

                                article = ArticleRecord(**article_data)

                                self._storage.append_article(
                                    article, self.country, self.source_key
                                )
                                articles_scraped += 1
                                self._scraped_urls_this_run.add(str(thumbnail.url))

                                if self.progress and (i + 1) % 10 == 0:
                                    self.progress.update(
                                        articles_scraped=articles_scraped,
                                        articles_failed=failed_http
                                        + failed_body
                                        + failed_date,
                                    )

                            except Exception as e:
                                logger.error(
                                    f"Failed to scrape article {thumbnail.url}: {e}"
                                )
                                failed_http += 1

                finally:
                    progress_bar.close()

        else:
            # Browser client implementation would go here
            pass

        # End-of-loop early-abort check: catches sources whose total thumbnail
        # count is below EARLY_ABORT_THRESHOLD. The mid-loop gate would never
        # have fired because the loop never reached that many iterations.
        # Per Q2=a, this also routes through the on_early_abort callback so
        # tiny sites get the same UX as bigger ones; the acknowledgement flag
        # ensures it doesn't re-prompt if the user already confirmed mid-loop.
        if articles_scraped == 0 and len(thumbnails) > 0:
            await self._check_early_abort(len(thumbnails))

        total_failed = failed_http + failed_body + failed_date
        logger.info(
            f"Scraped {articles_scraped} articles from {len(thumbnails)} thumbnails "
            f"({total_failed} failed: {failed_http} HTTP, {failed_body} body, {failed_date} date)"
        )

        return {
            "articles_scraped": articles_scraped,
            "filtered_listing": filtered_listing,
            "failed_http": failed_http,
            "failed_body": failed_body,
            "failed_date": failed_date,
            "warning_title": warning_title,
            "warning_tags": warning_tags,
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
        self.metrics.mode = "full_scrape"

        # Update progress: discovering phase
        if self.progress:
            self.progress.update(phase="discovering")

        try:
            # Initialize CSV file with headers before scraping
            csv_path = self._storage.initialize_csv(self.country, self.source_key)
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

            # Update metrics for discovered URLs
            self.metrics.urls_discovered = len(thumbnails)

            # Update progress: scraping phase
            if self.progress:
                self.progress.update(phase="scraping", urls_found=len(thumbnails))

            # Step 3: Build articles with streaming CSV writes
            articles_stats = {}
            if self.prefetched_articles:
                logger.info(
                    f"Using {len(self.prefetched_articles)} prefetched articles from API JSON; skipping HTML article scraping"
                )
                # Stream write prefetched articles to CSV
                for article in self.prefetched_articles:
                    self._storage.append_article(article, self.country, self.source_key)
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
                        "new_urls_discovered": len(thumbnails),
                        "articles_scraped": articles_stats.get("articles_scraped", 0),
                        "filtered_listing": articles_stats.get("filtered_listing", 0),
                        "failed_http": articles_stats.get("failed_http", 0),
                        "failed_body": articles_stats.get("failed_body", 0),
                        "failed_date": articles_stats.get("failed_date", 0),
                        "warning_title": articles_stats.get("warning_title", 0),
                        "warning_tags": articles_stats.get("warning_tags", 0),
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
                    self.failed_urls, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            if self.failed_news:
                saved_path = self._storage.save_failed_news(
                    self.failed_news, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["failed_news"] = saved_path

            # Save metadata - let storage handle serialization
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["metadata"] = saved_path
            except Exception as e:
                logger.error(f"Failed to save metadata: {e}")
                raise

            # Update metrics
            self.metrics.articles_scraped = articles_stats.get("articles_scraped", 0)
            self.metrics.articles_failed = articles_stats.get("articles_failed", 0)

            # Update progress: completed phase
            if self.progress:
                self.progress.update(
                    phase="completed",
                    articles_scraped=articles_stats.get("articles_scraped", 0),
                    articles_failed=articles_stats.get("articles_failed", 0),
                )

            logger.info(
                f"Scraping completed for {self.name}: {articles_stats.get('articles_scraped', 0)} articles scraped"
            )
            return results

        except EarlyAbortError:
            # Propagate so collect.py marks the source failed and continues
            # the plan. Do NOT swallow into an error_results dict.
            if self.progress:
                self.progress.update(phase="failed")
            raise
        except Exception as e:
            logger.error(f"Scraping failed for {self.name}: {e}")
            # Update progress: failed phase
            if self.progress:
                self.progress.update(phase="failed")
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
            # Step 1: Load ledgers
            # Seen ledger: urls.csv (used for stopping discovery and defining the scrape set)
            # Success ledger: news.csv (optional safety guard to avoid duplicate scraping)

            # Bootstrap urls.csv from news.csv if needed
            self._storage.ensure_urls_csv_from_news(self.country, self.source_key)

            urls_csv_seen = self._storage.get_existing_urls(
                self.country, self.source_key
            )
            scraped_urls = self._storage.get_existing_article_urls(
                self.country, self.source_key
            )

            # Effective seen set: urls.csv (discovery ledger) plus news.csv (always seen if scraped).
            # This keeps update runs stable even if urls.csv is missing or was previously truncated.
            seen_urls_at_start = set(urls_csv_seen)
            if scraped_urls:
                seen_urls_at_start |= set(scraped_urls)

            logger.info(
                f"Seen URLs (urls.csv): {len(urls_csv_seen)}; "
                f"Scraped URLs (news.csv): {len(scraped_urls)}"
            )

            # Reset prefetched articles for this run
            self.prefetched_articles = []

            # Step 2: Discover thumbnails batch-by-batch using seen-ledger stopping.
            # Stop when a whole batch is already present in urls.csv (seen URLs).
            all_thumbnails = await self._discover_thumbnails_incremental(
                existing_urls=seen_urls_at_start,
                check_existing=True,
            )

            # Identify newly discovered thumbnails relative to seen-at-start
            new_thumbnails: List[ThumbnailRecord] = []
            new_urls_seen: set[str] = set()
            for thumb in all_thumbnails:
                u = str(thumb.url)
                if u in seen_urls_at_start:
                    continue
                if u in new_urls_seen:
                    continue
                new_urls_seen.add(u)
                new_thumbnails.append(thumb)

            skipped_seen_count = len(all_thumbnails) - len(new_thumbnails)
            logger.info(
                f"Discovery complete. Total: {len(all_thumbnails)} thumbnails; "
                f"New (not seen at start): {len(new_thumbnails)}; "
                f"Seen skipped: {skipped_seen_count}"
            )

            # Persist only newly discovered URLs to urls.csv (deduplicated merge)
            if new_thumbnails:
                saved_path = self._storage.append_thumbnails_to_urls(
                    new_thumbnails, self.country, self.source_key
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

            # Optional safety guard: do not re-scrape URLs already in news.csv
            if scraped_urls and new_thumbnails:
                before = len(new_thumbnails)
                new_thumbnails = [
                    t for t in new_thumbnails if str(t.url) not in scraped_urls
                ]
                guard_skipped = before - len(new_thumbnails)
                if guard_skipped:
                    logger.info(
                        f"Safety guard: skipping {guard_skipped} URL(s) already present in news.csv"
                    )

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
                    self._storage.append_article(article, self.country, self.source_key)
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
                self._storage.get_newspaper_dir(self.country, self.source_key)
                / "news.csv"
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
                        "seen_urls_count": len(urls_csv_seen),
                        "scraped_urls_count": len(scraped_urls),
                        "new_discovered_count": len(new_thumbnails),
                        "seen_urls_skipped": skipped_seen_count,
                        "articles_scraped": new_articles_count,
                        "articles_failed": new_articles_failed,
                        "total_articles_after_update": len(scraped_urls)
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
                    self.failed_urls, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            if self.failed_news:
                saved_path = self._storage.save_failed_news(
                    self.failed_news, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["failed_news"] = saved_path

            # Save metadata
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.source_key, metadata_type="update"
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

        except EarlyAbortError:
            # Propagate so callers (collect.py et al.) mark the source failed.
            raise
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
                    self.failed_urls, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["failed_urls"] = saved_path

            # Save metadata
            try:
                saved_path = self._storage.save_metadata(
                    results, self.country, self.source_key, metadata_type="urls_only"
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

    def _update_failure_ledger(self, pending_thumbnails: List[ThumbnailRecord]) -> None:
        """
        Upsert this run's failures into ``failed_urls_seen.csv`` and evict any
        URLs we just succeeded on.

        A URL counts as failed for this run when it was in the ``pending`` set
        passed to ``scrape_articles`` but did not end up in ``news.csv``. This
        captures every failure mode — HTTP error, empty body, empty date,
        parse exception — under one ledger entry per URL per run, regardless
        of which ``self.failed_*`` list it landed on (or didn't).
        """
        scraped = set(self._scraped_urls_this_run)
        attempted = {
            str(t.url) for t in pending_thumbnails
        } - self._cancelled_by_watchdog
        failed = attempted - scraped

        if failed:
            # Build a status/error lookup from the existing failed_urls /
            # failed_news lists so the ledger row carries the most descriptive
            # error string we have available. Empty-body / empty-date paths
            # don't populate those lists today, so those URLs land with empty
            # status / error — that's fine, the ledger only needs the URL.
            status_by_url: Dict[str, str] = {}
            error_by_url: Dict[str, str] = {}
            for entry in (self.failed_urls or []) + (self.failed_news or []):
                u = entry.get("url")
                if not u:
                    continue
                key = str(u)
                if entry.get("status_code") is not None:
                    status_by_url[key] = str(entry.get("status_code"))
                if entry.get("error") is not None:
                    error_by_url[key] = str(entry.get("error"))

            entries = [
                {
                    "url": url,
                    "last_status": status_by_url.get(url, ""),
                    "last_error": error_by_url.get(url, ""),
                }
                for url in failed
            ]
            try:
                self._storage.upsert_failed_urls_ledger(
                    self.country, self.source_key, entries
                )
            except Exception as exc:
                logger.error(f"Failed to upsert failure ledger: {exc}")

        if scraped:
            try:
                removed = self._storage.evict_from_failed_ledger(
                    self.country, self.source_key, scraped
                )
                if removed:
                    logger.info(
                        f"Evicted {removed} URL(s) from failed_urls_seen.csv after success"
                    )
            except Exception as exc:
                logger.error(f"Failed to evict from failure ledger: {exc}")

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
        print("  Discovering thumbnails...", flush=True)
        client = self._get_http_client()
        thumbnail_selector = self.thumbnail_selectors.container
        all_thumbnails: List[ThumbnailRecord] = []
        previous_batch_data = None
        prev_batch_urls_window: List[set] = []
        no_progress_streak = 0

        async for result_batch in self.listing_strategy.discover_and_scrape(
            client, self.base_url, thumbnail_selector
        ):
            batch_thumbnails: List[ThumbnailRecord] = []

            # Handle API strategy's direct return of dicts
            if isinstance(self.listing_strategy, ApiStrategy):
                for thumb_data in result_batch:
                    # Use unified processing method
                    thumbnail = self._process_api_thumbnail(thumb_data)

                    if thumbnail:
                        batch_thumbnails.append(thumbnail)

                        # Handle prefetched articles
                        if thumb_data.get("body"):
                            article_dict = {
                                "url": str(thumbnail.url),
                                "title": thumbnail.title,
                                "date": thumbnail.date or "",
                                "body": thumb_data.get("body", ""),
                                "tags": thumb_data.get("tags", []),
                                "source": self.name,
                                "country": self.country,
                                "language": self.language,
                            }
                            try:
                                article = ArticleRecord(**article_dict)
                                self.prefetched_articles.append(article)
                            except Exception as e:
                                logger.error(
                                    f"Failed to create ArticleRecord from API data: {e}"
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
                            thumbnail = self._process_html_thumbnail(
                                thumb_data, stage="discovery"
                            )
                            if thumbnail:
                                batch_thumbnails.append(thumbnail)
                                self._maybe_prefetch_feed_body(thumb_elem, thumbnail)

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

                # Rule 5: Subtract last 2 batches' URLs (sticky widget noise:
                # sidebar/related/popular blocks that repeat across pages)
                # before checking for genuinely new URLs. Stops after 3
                # consecutive batches with zero truly-new content.
                widget_noise = (
                    set().union(*prev_batch_urls_window)
                    if prev_batch_urls_window
                    else set()
                )
                truly_new = batch_urls - widget_noise - existing_urls
                if not truly_new:
                    no_progress_streak += 1
                    if no_progress_streak >= 3:
                        logger.info(
                            "3 consecutive batches with no truly-new URLs "
                            "after widget filter. Stopping discovery."
                        )
                        break
                else:
                    no_progress_streak = 0
                prev_batch_urls_window.append(batch_urls)
                prev_batch_urls_window = prev_batch_urls_window[-2:]

            # Add to results
            all_thumbnails.extend(batch_thumbnails)
            previous_batch_data = batch_data

            # Update progress after each batch to keep progress file fresh
            if self.progress:
                self.progress.update(urls_found=len(all_thumbnails))

        logger.info(f"Total thumbnails discovered: {len(all_thumbnails)}")

        # Log any filter stats once per run
        self._log_filter_stats(stage="discovery")
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
        self.metrics.mode = "discover"

        # Update progress: discovering phase
        if self.progress:
            self.progress.update(phase="discovering")

        try:
            # Step 1: Ensure urls.csv exists
            created = self._storage.ensure_urls_csv_from_news(
                self.country, self.source_key
            )
            if created:
                logger.info("Created urls.csv from existing news.csv")

            # Step 2: Load existing URLs from urls.csv
            existing_urls = self._storage.get_existing_urls(
                self.country, self.source_key
            )
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
                    new_thumbnails, self.country, self.source_key
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
                results, self.country, self.source_key, metadata_type="discover"
            )

            # Update metrics
            self.metrics.urls_discovered = len(new_thumbnails)

            # Update progress: completed phase (no scraping in discover mode)
            if self.progress:
                self.progress.update(
                    phase="completed",
                    urls_found=len(new_thumbnails),
                    articles_scraped=0,
                    articles_failed=0,
                )

            logger.info(
                f"DISCOVER mode completed: {len(new_thumbnails)} new URLs found"
            )
            return results

        except Exception as e:
            logger.error(f"DISCOVER mode failed for {self.name}: {e}")
            # Update progress: failed phase
            if self.progress:
                self.progress.update(phase="failed")
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
        self.metrics.mode = "discover_full"

        # Update progress: discovering phase
        if self.progress:
            self.progress.update(phase="discovering")

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
                    all_thumbnails, self.country, self.source_key
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
                results, self.country, self.source_key, metadata_type="discover_full"
            )

            # Update metrics
            self.metrics.urls_discovered = len(all_thumbnails)

            # Update progress: completed phase (no scraping in discover_full mode)
            if self.progress:
                self.progress.update(
                    phase="completed",
                    urls_found=len(all_thumbnails),
                    articles_scraped=0,
                    articles_failed=0,
                )

            logger.info(
                f"DISCOVER-FULL mode completed: {len(all_thumbnails)} URLs found"
            )
            return results

        except Exception as e:
            logger.error(f"DISCOVER-FULL mode failed for {self.name}: {e}")
            # Update progress: failed phase
            if self.progress:
                self.progress.update(phase="failed")
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
        self.metrics.mode = "resume"

        # Update progress: scraping phase (no discovery in resume mode)
        if self.progress:
            self.progress.update(phase="scraping")

        try:
            # Step 1: Ensure urls.csv exists
            created = self._storage.ensure_urls_csv_from_news(
                self.country, self.source_key
            )
            if created:
                logger.info("Created urls.csv from existing news.csv")

            # Step 2: Load URLs from urls.csv
            thumbnails = self._storage.load_urls_from_csv(self.country, self.source_key)
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
                self.country, self.source_key
            )
            logger.info(
                f"Found {len(existing_article_urls)} existing articles in news.csv"
            )

            # Step 4: Identify pending articles
            # pending = urls.csv − news.csv − failed_urls_seen.csv (the latter
            # only when --retry-failed was not passed). The ledger is the
            # cumulative skip list of URLs that have already failed at least
            # once and not since succeeded.
            ledger_urls: set = set()
            if not self.retry_failed:
                ledger_urls = self._storage.get_failed_url_set(
                    self.country, self.source_key
                )
                logger.info(
                    f"Skipping {len(ledger_urls)} URL(s) per failed_urls_seen.csv ledger"
                )
            skip_set = existing_article_urls | ledger_urls
            pending_thumbnails = [
                thumb for thumb in thumbnails if str(thumb.url) not in skip_set
            ]
            skipped_by_ledger = (
                0
                if self.retry_failed
                else max(len(skip_set) - len(existing_article_urls), 0)
            )
            logger.info(f"Pending articles to scrape: {len(pending_thumbnails)}")

            # Newest-first so time-bounded runs capture recent articles before
            # older backfill. Undated thumbnails fall to the tail.
            pending_thumbnails.sort(
                key=lambda t: getattr(t, "date", "") or "", reverse=True
            )

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
                        "skipped_by_ledger": skipped_by_ledger,
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
                self._storage.get_newspaper_dir(self.country, self.source_key)
                / "news.csv"
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
                    "skipped_by_ledger": skipped_by_ledger,
                },
            }

            # Save failed news if any
            if self.failed_news:
                self._storage.save_failed_news(
                    self.failed_news, self.country, self.source_key
                )

            # Update the cumulative ledger: upsert this run's failures, then
            # evict any URLs we just succeeded on. Order matters — eviction
            # after upsert ensures a URL that succeeded this run never lingers
            # in the ledger even if it had also been recorded as failed.
            self._update_failure_ledger(pending_thumbnails)

            # Save metadata
            self._storage.save_metadata(
                results, self.country, self.source_key, metadata_type="resume"
            )

            # Update metrics
            self.metrics.articles_scraped = scrape_stats.get("articles_scraped", 0)
            self.metrics.articles_failed = scrape_stats.get("articles_failed", 0)

            # Update progress: completed phase
            if self.progress:
                self.progress.update(
                    phase="completed",
                    urls_found=len(pending_thumbnails),
                    articles_scraped=scrape_stats.get("articles_scraped", 0),
                    articles_failed=scrape_stats.get("articles_failed", 0),
                )

            logger.info(
                f"RESUME mode completed: {scrape_stats.get('articles_scraped', 0)} articles scraped"
            )
            return results

        except EarlyAbortError:
            # Propagate so callers mark the source failed and continue.
            if self.progress:
                self.progress.update(phase="failed")
            raise
        except Exception as e:
            logger.error(f"RESUME mode failed for {self.name}: {e}")
            # Update progress: failed phase
            if self.progress:
                self.progress.update(phase="failed")
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
        self.metrics.mode = "default"

        # Update progress: discovering phase
        if self.progress:
            self.progress.update(phase="discovering")

        try:
            # Step 1: Ensure urls.csv exists
            created = self._storage.ensure_urls_csv_from_news(
                self.country, self.source_key
            )
            if created:
                logger.info("Created urls.csv from existing news.csv")

            # Step 2: Load existing URLs from urls.csv
            existing_urls = self._storage.get_existing_urls(
                self.country, self.source_key
            )
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
                    new_thumbnails, self.country, self.source_key
                )
                if saved_path:
                    self._saved_files["urls"] = saved_path
                logger.info(f"Appended {len(new_thumbnails)} new URLs to urls.csv")

            # Update metrics for discovered URLs
            self.metrics.urls_discovered = len(new_thumbnails)

            # Update progress: scraping phase
            if self.progress:
                self.progress.update(phase="scraping", urls_found=len(new_thumbnails))

            # Step 5: Load existing article URLs from news.csv
            existing_article_urls = self._storage.get_existing_article_urls(
                self.country, self.source_key
            )
            logger.info(f"Found {len(existing_article_urls)} existing articles")

            # Step 6: Identify pending articles (all urls.csv - news.csv)
            # Reload urls.csv to get complete list including newly added
            all_thumbnails = self._storage.load_urls_from_csv(
                self.country, self.source_key
            )
            if all_thumbnails is None:
                all_thumbnails = []

            # pending = urls.csv − news.csv − failed_urls_seen.csv (unless
            # --retry-failed). See run_resume for the same logic.
            ledger_urls: set = set()
            if not self.retry_failed:
                ledger_urls = self._storage.get_failed_url_set(
                    self.country, self.source_key
                )
                logger.info(
                    f"Skipping {len(ledger_urls)} URL(s) per failed_urls_seen.csv ledger"
                )
            skip_set = existing_article_urls | ledger_urls
            pending_thumbnails = [
                thumb for thumb in all_thumbnails if str(thumb.url) not in skip_set
            ]
            skipped_by_ledger = (
                0
                if self.retry_failed
                else max(len(skip_set) - len(existing_article_urls), 0)
            )
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
                        self._storage.append_article(
                            article, self.country, self.source_key
                        )
                        self._scraped_urls_this_run.add(str(article.url))
                        articles_from_api += 1

                # Remove prefetched URLs from pending
                prefetched_urls = {str(a.url) for a in self.prefetched_articles}
                pending_thumbnails = [
                    t for t in pending_thumbnails if str(t.url) not in prefetched_urls
                ]

            # Newest-first so time-bounded runs capture recent articles before
            # older backfill. Undated thumbnails fall to the tail.
            pending_thumbnails.sort(
                key=lambda t: getattr(t, "date", "") or "", reverse=True
            )

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
            scrape_stats = {
                "articles_scraped": 0,
                "filtered_listing": 0,
                "failed_http": 0,
                "failed_body": 0,
                "failed_date": 0,
                "warning_title": 0,
                "warning_tags": 0,
                "total_attempted": 0,
            }
            if pending_thumbnails:
                scrape_stats = await self.scrape_articles(pending_thumbnails)

            total_scraped = scrape_stats.get("articles_scraped", 0) + articles_from_api

            # Mark articles file as saved
            csv_path = (
                self._storage.get_newspaper_dir(self.country, self.source_key)
                / "news.csv"
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
                    "filtered_listing": scrape_stats.get("filtered_listing", 0),
                    "failed_http": scrape_stats.get("failed_http", 0),
                    "failed_body": scrape_stats.get("failed_body", 0),
                    "failed_date": scrape_stats.get("failed_date", 0),
                    "warning_title": scrape_stats.get("warning_title", 0),
                    "warning_tags": scrape_stats.get("warning_tags", 0),
                    "failed_urls": len(self.failed_urls),
                    "failed_news": len(self.failed_news),
                    "skipped_by_ledger": skipped_by_ledger,
                },
            }

            # Save failed URLs and news if any
            if self.failed_urls:
                self._storage.save_failed_urls(
                    self.failed_urls, self.country, self.source_key
                )
            if self.failed_news:
                self._storage.save_failed_news(
                    self.failed_news, self.country, self.source_key
                )

            # Cumulative failure ledger: upsert this run's failures, then evict
            # successes. See _update_failure_ledger.
            self._update_failure_ledger(pending_thumbnails)

            # Save metadata
            self._storage.save_metadata(
                results, self.country, self.source_key, metadata_type="default"
            )

            # Update metrics
            self.metrics.articles_scraped = total_scraped
            self.metrics.articles_failed = scrape_stats.get("articles_failed", 0)

            # Update progress: completed phase
            if self.progress:
                self.progress.update(
                    phase="completed",
                    articles_scraped=total_scraped,
                    articles_failed=scrape_stats.get("articles_failed", 0),
                )

            logger.info(
                f"DEFAULT mode completed: {len(new_thumbnails)} new URLs, "
                f"{total_scraped} articles scraped"
            )
            return results

        except EarlyAbortError:
            # Propagate so collect.py marks the source failed and continues
            # the plan. Do NOT swallow into an error result dict.
            if self.progress:
                self.progress.update(phase="failed")
            raise
        except Exception as e:
            logger.error(f"DEFAULT mode failed for {self.name}: {e}")
            # Update progress: failed phase
            if self.progress:
                self.progress.update(phase="failed")
            return {
                "success": False,
                "newspaper": self.name,
                "country": self.country,
                "mode": "default",
                "error": str(e),
            }
