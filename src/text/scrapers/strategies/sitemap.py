"""
Sitemap-based listing strategy.

Fetches article URLs from XML sitemaps, either via a sitemap index that points
at sub-sitemaps, or from an explicit list of sitemap URLs. Useful for news
sites without working pagination or date-archive URLs.
"""

import asyncio
import gzip
import logging
import re
from typing import List, Dict, Any, Optional, AsyncGenerator

import httpx
from bs4 import BeautifulSoup

from .base import ListingStrategy
from ..models import ScrapingResult

logger = logging.getLogger(__name__)


class SitemapStrategy(ListingStrategy):
    """
    Sitemap-based listing strategy.

    Config keys:
    - sitemap_index_url: URL of a sitemapindex file (optional)
    - sitemap_urls: explicit list of sitemap URLs (optional; can be combined
      with sitemap_index_url)
    - sitemap_regex: regex filter applied to sub-sitemap URLs from the index
      (optional)
    - url_regex: regex filter applied to <loc> values inside each sub-sitemap
      (optional)
    - url_replace: dict with "pattern" and "replacement" applied via re.sub to
      each <loc> before yielding. Useful for sites whose sitemap only indexes
      one language variant. (optional)

    Thumbnail selectors in the YAML should target the <url> container and its
    <loc>/<lastmod> children, e.g.:
        container: "url"
        url: "loc::text"
        title: "loc::text"
        date: "lastmod::text"
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        super().__init__(config, max_pages)

        self.sitemap_index_url = config.get("sitemap_index_url")
        explicit = config.get("sitemap_urls") or []
        if isinstance(explicit, str):
            explicit = [explicit]
        self.sitemap_urls: List[str] = list(explicit)

        if not self.sitemap_index_url and not self.sitemap_urls:
            raise ValueError(
                "sitemap strategy requires sitemap_index_url or sitemap_urls"
            )

        self.sitemap_regex = (
            re.compile(config["sitemap_regex"]) if config.get("sitemap_regex") else None
        )
        self.url_regex = (
            re.compile(config["url_regex"]) if config.get("url_regex") else None
        )

        url_replace = config.get("url_replace") or {}
        self.url_replace_pattern = (
            re.compile(url_replace["pattern"]) if url_replace.get("pattern") else None
        )
        self.url_replace_repl = url_replace.get("replacement", "")

    async def _fetch(self, client, url: str) -> Optional[str]:
        async with httpx.AsyncClient() as http_client:
            content, _ = await client.request_url(http_client, url)
        if content is None:
            return None
        if isinstance(content, bytes):
            # Transparently decompress gzipped sitemaps (.xml.gz served as octet-stream)
            if content[:2] == b"\x1f\x8b":
                try:
                    content = gzip.decompress(content)
                except OSError as e:
                    logger.warning(f"Failed to gunzip sitemap {url}: {e}")
                    return None
            return content.decode("utf-8", errors="replace")
        return content

    async def _resolve_sitemaps(self, client) -> List[str]:
        sitemaps: List[str] = list(self.sitemap_urls)

        if self.sitemap_index_url:
            logger.info(f"Fetching sitemap index: {self.sitemap_index_url}")
            content = await self._fetch(client, self.sitemap_index_url)
            if not content:
                logger.warning(
                    f"Failed to fetch sitemap index: {self.sitemap_index_url}"
                )
            else:
                soup = BeautifulSoup(content, "html.parser")
                for sm_tag in soup.select("sitemap"):
                    loc = sm_tag.select_one("loc")
                    if not loc:
                        continue
                    url = loc.get_text(strip=True)
                    if self.sitemap_regex and not self.sitemap_regex.search(url):
                        continue
                    sitemaps.append(url)

        # Dedupe while preserving none-first then sort newest-first
        sitemaps = sorted(set(sitemaps), reverse=True)
        return sitemaps

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List[ScrapingResult], None]:
        sitemaps = await self._resolve_sitemaps(client)
        logger.info(f"Sitemap strategy: {len(sitemaps)} sub-sitemaps queued")

        processed = 0
        for sm_url in sitemaps:
            if self.max_pages is not None and processed >= self.max_pages:
                logger.info(f"Reached max_pages limit ({self.max_pages})")
                break

            content = await self._fetch(client, sm_url)
            if not content:
                logger.warning(f"Failed to fetch sub-sitemap: {sm_url}")
                continue

            soup = BeautifulSoup(content, "html.parser")
            elements = soup.select(thumbnail_selector)

            # Apply url_replace to rewrite each <loc> value in place
            if self.url_replace_pattern is not None:
                for el in elements:
                    loc = el.select_one("loc")
                    if loc is None:
                        continue
                    original = loc.get_text(strip=True)
                    rewritten = self.url_replace_pattern.sub(
                        self.url_replace_repl, original
                    )
                    loc.string = rewritten

            if self.url_regex:
                filtered = []
                for el in elements:
                    loc = el.select_one("loc")
                    if loc and self.url_regex.search(loc.get_text(strip=True)):
                        filtered.append(el)
                elements = filtered

            logger.info(f"Sub-sitemap {sm_url}: {len(elements)} URLs")
            if not elements:
                continue

            yield [
                ScrapingResult(
                    success=True, data=elements, status_code=200, url=sm_url
                )
            ]
            processed += 1
            await asyncio.sleep(0.3)

        logger.info(f"Sitemap strategy completed: {processed} sub-sitemaps yielded")
