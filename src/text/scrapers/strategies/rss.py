"""
RSS/Atom feed listing strategy.

Fetches article URLs from RSS 2.0 / Atom / RDF feeds. Feeds are parsed with the
lxml XML parser (NOT html.parser, which treats <link> as a void element and drops
its text content). Useful for sites without working pagination or a WordPress API,
and for lightweight incremental refresh of recent articles. Feeds are typically
front-page-only (10-50 most recent items); set page_param only for feeds that
actually serve older items on ?paged=N.
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, AsyncGenerator

import httpx
from bs4 import BeautifulSoup

from .base import ListingStrategy
from ..models import ScrapingResult

logger = logging.getLogger(__name__)


class RssStrategy(ListingStrategy):
    """
    RSS/Atom feed listing strategy.

    Config keys:
    - feed_urls: str or list of feed URLs (required).
    - url_regex: optional regex; only items whose <link> matches are kept.
    - page_param: optional query param (e.g. "paged") to walk older items. Each
      feed URL is requested with ?<page_param>=N until a page yields no new items
      or max_pages is reached. Leave unset for the common front-page-only feed.
    - body_in_feed: optional bool. When true, the article body is read straight
      from the feed item (content:encoded, then description) and the article-page
      fetch is skipped. Items without an in-feed body fall back to the article page.
    - feed_body_tags: optional list overriding which tags carry the body.

    Thumbnail selectors in the YAML target the item's children. Selector matching
    is case-sensitive under the XML parser, so use exact tag case. RSS 2.0:
        container: "item"
        url: "link::text"
        title: "title::text"
        date: "pubDate::text"
    Atom:
        container: "entry"
        url: "link::attr(href)"
        title: "title::text"
        date: "published::text"
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        super().__init__(config, max_pages)

        feeds = config.get("feed_urls") or []
        if isinstance(feeds, str):
            feeds = [feeds]
        self.feed_urls: List[str] = list(feeds)
        if not self.feed_urls:
            raise ValueError("rss strategy requires feed_urls")

        self.url_regex = (
            re.compile(config["url_regex"]) if config.get("url_regex") else None
        )
        self.page_param = config.get("page_param")
        self.rate_limit = float(config.get("rate_limit", 0.3))

        self.body_in_feed = bool(config.get("body_in_feed", False))
        self.feed_body_tags = config.get("feed_body_tags") or [
            "content:encoded",
            "description",
        ]

    def extract_body(self, el) -> str:
        """
        Extract the article body from a feed item, when the feed carries it.

        Tries each tag in feed_body_tags in order (default content:encoded, then
        description). content:encoded/description hold CDATA-wrapped HTML, so the
        raw string is re-parsed with html.parser and flattened to text. Returns ""
        when no tag yields usable text; the caller then falls back to the article page.
        """
        for tag in self.feed_body_tags:
            node = el.find(tag)
            if node is None:
                continue
            raw = node.get_text()
            if not raw or not raw.strip():
                continue
            text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
            if text:
                return text
        return ""

    async def _fetch(self, client, url: str) -> Optional[str]:
        async with httpx.AsyncClient() as http_client:
            content, _ = await client.request_url(http_client, url)
        if content is None:
            return None
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return content

    @staticmethod
    def _item_url(el) -> Optional[str]:
        link = el.find("link")
        if link is None:
            return None
        text = link.get_text(strip=True)
        if text:
            return text
        href = link.get("href")
        return href.strip() if href else None

    def _page_urls(self, feed_url: str):
        if not self.page_param:
            yield feed_url
            return
        limit = self.max_pages or 50
        sep = "&" if "?" in feed_url else "?"
        for n in range(1, limit + 1):
            yield f"{feed_url}{sep}{self.page_param}={n}"

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List[ScrapingResult], None]:
        seen: set = set()
        pages_done = 0

        for feed_url in self.feed_urls:
            for page_url in self._page_urls(feed_url):
                if self.max_pages is not None and pages_done >= self.max_pages:
                    logger.info(f"Reached max_pages limit ({self.max_pages})")
                    return

                content = await self._fetch(client, page_url)
                if not content:
                    logger.warning(f"Failed to fetch feed: {page_url}")
                    break

                soup = BeautifulSoup(content, "xml")
                elements = soup.select(thumbnail_selector)

                fresh = []
                for el in elements:
                    url = self._item_url(el)
                    if url is None or url in seen:
                        continue
                    if self.url_regex and not self.url_regex.search(url):
                        continue
                    seen.add(url)
                    fresh.append(el)

                logger.info(f"Feed {page_url}: {len(elements)} items, {len(fresh)} new")
                pages_done += 1

                if not fresh:
                    break

                yield [
                    ScrapingResult(
                        success=True, data=fresh, status_code=200, url=page_url
                    )
                ]
                await asyncio.sleep(self.rate_limit)

        logger.info(f"RSS strategy completed: {pages_done} feed pages yielded")
