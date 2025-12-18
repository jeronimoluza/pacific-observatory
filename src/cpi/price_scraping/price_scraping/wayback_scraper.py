"""
Wayback Machine scraper for historical product data.
Fetches archived versions of product URLs and extracts data using spider selectors.
Uses parallel processing with queues to decouple snapshot fetching and parsing.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import hashlib
import threading
import queue
import time
import subprocess

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .selectors import get_selectors, extract_with_fallback

logger = logging.getLogger(__name__)


class WaybackScraper:
    """Scrapes historical product data from Wayback Machine archives."""

    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, spider_name: str, output_dir: Path, from_date: str):
        """
        Initialize Wayback Machine scraper.

        Args:
            spider_name: Name of the spider (e.g., 'rbpatel')
            output_dir: Base output directory for scraped data
            from_date: End timestamp for wayback snapshots (YYYY-MM-DD format)
        """
        self.spider_name = spider_name
        self.output_dir = Path(output_dir)
        self.from_date = from_date
        self.selectors = get_selectors(spider_name)
        self.scraped_at = datetime.now().isoformat()
        self._file_write_lock = threading.Lock()  # Lock for thread-safe file writing

    def _get_url_hash(self, url: str) -> str:
        """Generate hash for URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_existing_url_hashes(self, country: str, stage: str = "items") -> set:
        """
        Get set of URL hashes that already have saved wayback data.

        Args:
            country: Country code for directory structure
            stage: 'snapshots' or 'items' - which stage to check for existing data

        Returns:
            Set of existing URL hashes
        """
        wayback_dir = (
            self.output_dir
            / country
            / self.spider_name
            / "wayback_machine_data"
            / stage
        )
        existing_hashes = set()

        if wayback_dir.exists():
            for json_file in wayback_dir.glob("*.json"):
                # Extract hash from filename (e.g., "b9f46c47a99e6b42b9cf70700e05b8f5.json")
                url_hash = json_file.stem
                existing_hashes.add(url_hash)

        return existing_hashes

    def _load_snapshots(self, url_hash: str, country: str) -> Optional[List[str]]:
        """
        Load previously fetched snapshots from file.

        Args:
            url_hash: Hash of the URL
            country: Country code for directory structure

        Returns:
            List of wayback URLs or None if file doesn't exist
        """
        snapshots_file = (
            self.output_dir
            / country
            / self.spider_name
            / "wayback_machine_data"
            / "snapshots"
            / f"{url_hash}.json"
        )

        if snapshots_file.exists():
            try:
                with open(snapshots_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load snapshots from {snapshots_file}: {e}")

        return None

    def _save_snapshots(
        self, url_hash: str, snapshots: List[str], country: str
    ) -> Path:
        """
        Save fetched snapshots to JSON file (thread-safe).

        Args:
            url_hash: Hash of the URL
            snapshots: List of wayback archive URLs
            country: Country code for directory structure

        Returns:
            Path to saved file
        """
        with self._file_write_lock:
            snapshots_dir = (
                self.output_dir
                / country
                / self.spider_name
                / "wayback_machine_data"
                / "snapshots"
            )
            snapshots_dir.mkdir(parents=True, exist_ok=True)

            snapshots_file = snapshots_dir / f"{url_hash}.json"

            with open(snapshots_file, "w", encoding="utf-8") as f:
                json.dump(snapshots, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved {len(snapshots)} snapshots to {snapshots_file}")
            return snapshots_file

    def _extract_data_from_html(self, html_content: str, url: str) -> Dict[str, Any]:
        """
        Extract product data from HTML using spider selectors with fallback support.

        Args:
            html_content: HTML content to parse
            url: Original URL for error logging

        Returns:
            Dictionary with extracted data
        """
        soup = BeautifulSoup(html_content, "html.parser")
        extracted = {}

        for field, selector_list in self.selectors.items():
            value = extract_with_fallback(soup, selector_list)
            if value:
                extracted[field] = value

        return extracted

    def _fetch_wayback_snapshots(self, url: str) -> List[str]:
        """
        Fetch all available Wayback Machine snapshots for a URL using curl and CDX API.
        Parses CDX API output and constructs wayback archive URLs.
        Only includes snapshots with HTTP 200 status code.

        Args:
            url: URL to fetch snapshots for

        Returns:
            List of wayback archive URLs
        """
        try:
            # Build CDX API query with end_timestamp filter
            # Use output=json to get structured data
            cdx_url = f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&filter=statuscode:200&sort=timestamp"
            if self.from_date:
                # Convert YYYY-MM-DD to YYYYMMDD format for CDX API
                from_date_formatted = self.from_date.replace("-", "")
                cdx_url += f"&to={from_date_formatted}"

            # Use curl to fetch CDX API response
            result = subprocess.run(
                [
                    "curl",
                    "-s",
                    "--connect-timeout",
                    "240",
                    "--max-time",
                    "1800",
                    "--retry",
                    "6",
                    "--retry-delay",
                    "60",
                    "--retry-max-time",
                    "1800",
                    "--retry-connrefused",
                    "--retry-all-errors",
                    cdx_url,
                ],
                capture_output=True,
                text=True,
                timeout=2000,
            )

            if result.returncode != 0:
                logger.warning(f"Curl failed for {url}: {result.stderr}")
                return []

            if result.stdout.strip() == "[]":
                logger.debug(f"No snapshots found for {url}")
                return []

            # Parse JSON response
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse CDX API response for {url}: {e}")
                return []

            # CDX API returns empty array [] when no snapshots found
            # CDX API JSON format with snapshots:
            # First row is header: ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length"]
            # Subsequent rows are data (need at least header + 1 data row)
            if not data or len(data) < 2:
                logger.debug(f"No snapshots found for {url}")
                return []

            # Find indices of timestamp and original columns from header
            header = data[0]
            try:
                timestamp_idx = header.index("timestamp")
                original_idx = header.index("original")
            except ValueError:
                logger.warning(f"CDX API response missing expected columns for {url}")
                return []

            snapshots = []
            seen_timestamps = set()
            for row in data[1:]:  # Skip header row
                if len(row) <= max(timestamp_idx, original_idx):
                    continue

                timestamp = row[timestamp_idx]
                original_url = row[original_idx]

                # Deduplicate by timestamp - skip if we've already seen this timestamp
                if timestamp in seen_timestamps:
                    logger.debug(
                        f"Skipping duplicate snapshot for {url} at {timestamp}"
                    )
                    continue

                seen_timestamps.add(timestamp)

                # Construct wayback archive URL
                wayback_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                snapshots.append(wayback_url)

            logger.debug(f"Found {len(snapshots)} unique snapshots for {url}")
            return snapshots

        except subprocess.TimeoutExpired:
            logger.warning(f"Curl timeout while fetching snapshots for {url}")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch snapshots for {url}: {e}")
            return []

    def _scrape_wayback_url(self, wayback_url: str) -> Optional[str]:
        """
        Fetch content from a Wayback Machine URL with retry logic.
        Retries up to 10 times with 5-second delays between attempts.

        Args:
            wayback_url: Wayback Machine archive URL

        Returns:
            HTML content or None if all retries fail
        """
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    wayback_url, timeout=120, headers={"User-Agent": self.USER_AGENT}
                )
                response.raise_for_status()
                if not response.text:
                    logger.debug(f"Empty response for {wayback_url}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
                return response.text
            except requests.exceptions.HTTPError as e:
                logger.debug(
                    f"HTTP error {e.response.status_code} for {wayback_url} (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
            except requests.exceptions.Timeout:
                logger.debug(
                    f"Timeout fetching {wayback_url} (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
            except Exception as e:
                logger.debug(
                    f"Failed to fetch {wayback_url} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None

        return None

    def _extract_timestamp_from_wayback_url(self, wayback_url: str) -> Optional[str]:
        """
        Extract timestamp from Wayback Machine URL.

        Args:
            wayback_url: Wayback Machine archive URL

        Returns:
            Timestamp in format YYYYMMDDHHMMSS or None
        """
        try:
            # Format: https://web.archive.org/web/20220928054939/https://...
            parts = wayback_url.split("/web/")
            if len(parts) > 1:
                timestamp = parts[1].split("/")[0]
                return timestamp
        except Exception as e:
            logger.debug(f"Failed to extract timestamp from {wayback_url}: {e}")
        return None

    def _snapshot_fetcher_worker(
        self,
        input_queue: queue.Queue,
        output_queue: queue.Queue,
        country: str,
        pbar_fetch: tqdm,
    ):
        """
        Worker thread that fetches snapshots from Wayback Machine and puts them in the output queue.
        Stores empty snapshots for URLs with no available snapshots to avoid re-fetching.

        Args:
            input_queue: Queue containing (url, url_hash) tuples
            output_queue: Queue to put (url_hash, snapshots) tuples
            country: Country code for directory structure
            pbar_fetch: Progress bar for snapshot fetching
        """
        while True:
            try:
                url, url_hash = input_queue.get(timeout=1)

                if url is None:  # Sentinel value to stop worker
                    break

                # Try to load existing snapshots first
                existing_snapshots = self._load_snapshots(url_hash, country)
                if existing_snapshots is not None:
                    # Found snapshots file (even if empty list)
                    logger.debug(
                        f"Loaded {len(existing_snapshots)} existing snapshots for {url_hash}"
                    )
                    output_queue.put((url_hash, existing_snapshots))
                    pbar_fetch.update(1)
                    input_queue.task_done()
                    continue

                # Fetch new snapshots
                try:
                    snapshots = self._fetch_wayback_snapshots(url)
                    # Save snapshots regardless of whether they're empty or not
                    # This prevents re-fetching URLs that have no snapshots
                    self._save_snapshots(url_hash, snapshots, country)

                    if snapshots:
                        logger.debug(f"Found {len(snapshots)} snapshots for {url}")
                    else:
                        logger.warning(
                            f"No snapshots found for {url} - storing empty list to avoid re-fetching"
                        )

                    output_queue.put((url_hash, snapshots))
                except Exception as e:
                    logger.error(f"Error fetching snapshots for {url}: {e}")
                    # Don't save on error - allow retry on next run
                    output_queue.put((url_hash, []))

                pbar_fetch.update(1)

                # Rate limiting for snapshot fetching
                # time.sleep(random.uniform(10, 20))

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in snapshot fetcher worker: {e}")
            finally:
                input_queue.task_done()

    def _parser_worker(
        self,
        input_queue: queue.Queue,
        country: str,
        url_hash_to_url: Dict[str, str],
        pbar_parse: tqdm,
        stats: Dict[str, Any],
    ):
        """
        Worker thread that parses snapshots and saves parsed items.

        Args:
            input_queue: Queue containing (url_hash, snapshots) tuples
            country: Country code for directory structure
            url_hash_to_url: Mapping of url_hash to original URL
            pbar_parse: Progress bar for parsing
            stats: Statistics dictionary to update
        """
        while True:
            try:
                item = input_queue.get(timeout=1)

                if item is None:  # Sentinel value to stop worker
                    input_queue.task_done()
                    break

                url_hash, snapshots = item

                if not snapshots:
                    pbar_parse.update(1)
                    input_queue.task_done()
                    continue

                # Parse snapshots
                results = []
                original_url = url_hash_to_url.get(url_hash, "unknown")
                failed_count = 0

                for wayback_url in snapshots:
                    try:
                        html_content = self._scrape_wayback_url(wayback_url)
                        if not html_content:
                            logger.debug(f"No HTML content for {wayback_url}")
                            failed_count += 1
                            continue

                        timestamp = self._extract_timestamp_from_wayback_url(
                            wayback_url
                        )
                        extracted_data = self._extract_data_from_html(
                            html_content, original_url
                        )

                        # Flatten extracted data into result object
                        result = {
                            "wayback_url": wayback_url,
                            "wayback_timestamp": timestamp,
                            "url_hash": url_hash,
                            "scraped_at": self.scraped_at,
                        }
                        # Add all extracted fields to the result
                        result.update(extracted_data)
                        results.append(result)
                    except Exception as e:
                        logger.debug(f"Error parsing snapshot {wayback_url}: {e}")
                        failed_count += 1
                        continue

                if failed_count > 0:
                    logger.warning(
                        f"Failed to parse {failed_count}/{len(snapshots)} snapshots for {url_hash} ({original_url})"
                    )

                # Save parsed items
                if results:
                    self._save_parsed_items(url_hash, results, country)
                    stats["successful_scrapes"] += 1
                    stats["total_snapshots"] += len(results)
                else:
                    stats["failed_scrapes"] += 1

                pbar_parse.update(1)
                input_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in parser worker: {e}")

    def _save_parsed_items(
        self, url_hash: str, data: List[Dict[str, Any]], country: str
    ) -> Path:
        """
        Save parsed items to JSON file (thread-safe).

        Args:
            url_hash: Hash of the URL
            data: List of wayback snapshots with extracted data
            country: Country code for directory structure

        Returns:
            Path to saved file
        """
        with self._file_write_lock:
            items_dir = (
                self.output_dir
                / country
                / self.spider_name
                / "wayback_machine_data"
                / "items"
            )
            items_dir.mkdir(parents=True, exist_ok=True)

            output_file = items_dir / f"{url_hash}.json"

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # logger.info(f"Saved parsed items to {output_file}")
            return output_file

    def run_scrape_wayback(
        self, items: List[Dict[str, Any]], country: str, num_parser_workers: int = 1
    ) -> Dict[str, Any]:
        """
        Run wayback machine scraping with parallel snapshot fetching and parsing.

        Uses two worker threads:
        1. Snapshot fetcher: Fetches snapshots from Wayback Machine CDX API
        2. Parser: Parses snapshots and extracts product data (sequential to avoid interleaving)

        Args:
            items: List of product items with URLs
            country: Country code for directory structure
            num_parser_workers: Number of parser worker threads (default: 1 for sequential processing)

        Returns:
            Summary statistics
        """
        # Deduplicate items by url_hash
        seen_hashes = set()
        unique_items = []
        url_hash_to_url = {}
        for item in items:
            url_hash = self._get_url_hash(item["url"])
            if url_hash not in seen_hashes:
                seen_hashes.add(url_hash)
                unique_items.append((item["url"], url_hash))
                url_hash_to_url[url_hash] = item["url"]

        # Get existing URL hashes to skip (only check items stage for final output)
        existing_items = self._get_existing_url_hashes(country, stage="items")
        items_to_scrape = [
            (url, url_hash)
            for url, url_hash in unique_items
            if url_hash not in existing_items
        ]

        logger.info(
            f"Processing {len(unique_items)} unique URLs from {len(items)} total items"
        )
        logger.info(
            f"Skipping {len(unique_items) - len(items_to_scrape)} URLs that already have parsed items"
        )
        logger.info(f"Scraping {len(items_to_scrape)} new URLs")

        stats = {
            "total_items": len(items),
            "unique_urls": len(unique_items),
            "skipped_urls": len(unique_items) - len(items_to_scrape),
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_snapshots": 0,
        }

        if not items_to_scrape:
            logger.info("No new URLs to scrape")
            return stats

        # Create queues for inter-thread communication
        snapshot_queue = queue.Queue()  # Input queue for snapshot fetcher
        parse_queue = queue.Queue()  # Output from fetcher, input to parser

        # Start snapshot fetcher thread
        pbar_fetch = tqdm(total=len(items_to_scrape), desc="Fetching snapshots")
        fetcher_thread = threading.Thread(
            target=self._snapshot_fetcher_worker,
            args=(snapshot_queue, parse_queue, country, pbar_fetch),
            daemon=True,
        )
        fetcher_thread.start()

        # Start parser worker threads
        pbar_parse = tqdm(total=len(items_to_scrape), desc="Parsing snapshots")
        parser_threads = []
        for _ in range(num_parser_workers):
            parser_thread = threading.Thread(
                target=self._parser_worker,
                args=(parse_queue, country, url_hash_to_url, pbar_parse, stats),
                daemon=True,
            )
            parser_thread.start()
            parser_threads.append(parser_thread)

        # Feed URLs to snapshot fetcher
        for url, url_hash in items_to_scrape:
            snapshot_queue.put((url, url_hash))

        # Wait for snapshot fetcher to finish
        snapshot_queue.join()
        pbar_fetch.close()

        # Send sentinel values to stop parser workers
        for _ in range(num_parser_workers):
            parse_queue.put(None)

        # Wait for all parser workers to finish
        for parser_thread in parser_threads:
            parser_thread.join()
        pbar_parse.close()

        # Send sentinel to stop fetcher
        snapshot_queue.put((None, None))
        fetcher_thread.join()

        logger.info(
            f"Scraping completed: {stats['successful_scrapes']} successful, {stats['failed_scrapes']} failed, {stats['total_snapshots']} total snapshots"
        )

        return stats
