"""Scrape Pickaroo (Philippines) - https://pickaroo.com/

Listing-first, location-aware crawl:

- Start at supermarket brand index.
- Enumerate brand pages, then explicit location pages.
- Extract product cards from location listings.
- Only hit product-detail pages when listing cards are missing required fields.
"""

import logging
import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import scrapy

from price_scraping.selectors import get_selectors
from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class PickarooSpider(scrapy.Spider):
    """Location-aware listing-first spider for Pickaroo."""

    name = "pickaroo"
    allowed_domains = ["pickaroo.com"]
    start_urls = ["https://pickaroo.com/groceries/brands/supermarket/"]
    country = "philippines"
    currency = "PHP"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("pickaroo")

    MAX_PAGES_PER_LOCATION = 40
    MAX_CONSECUTIVE_EMPTY_PAGES = 2

    _DENY_PATH_PARTS = (
        "cart",
        "checkout",
        "account",
        "login",
        "search",
        "groceries",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_pages: set[str] = set()
        self._empty_pages_by_location: dict[str, int] = defaultdict(int)

    def parse(self, response):
        for brand_url in self._extract_brand_urls(response):
            brand_slug = self._root_slug_from_url(brand_url) or "unknown"
            yield scrapy.Request(
                brand_url,
                callback=self.parse_brand,
                meta={"brand_slug": brand_slug},
            )

    def parse_brand(self, response):
        brand_slug = (
            response.meta.get("brand_slug")
            or self._root_slug_from_url(response.url)
            or "unknown"
        )
        for loc_url, location_slug in self._extract_location_urls(response, brand_slug):
            location_key = f"{brand_slug}:{location_slug}"
            yield scrapy.Request(
                loc_url,
                callback=self.parse_location,
                meta={
                    "brand_slug": brand_slug,
                    "location_slug": location_slug,
                    "location_key": location_key,
                    "page": 1,
                },
            )

    def parse_location(self, response):
        if response.url in self._seen_pages:
            return
        self._seen_pages.add(response.url)

        brand_slug = response.meta.get("brand_slug", "unknown")
        location_slug = response.meta.get("location_slug", "unknown")
        location_key = (
            response.meta.get("location_key") or f"{brand_slug}:{location_slug}"
        )
        page = response.meta.get("page", 1)

        category = f"{brand_slug} > {location_slug}"

        items_found = 0
        detail_fallbacks = 0
        for item_or_req in self._extract_listing_products(response, category):
            if isinstance(item_or_req, scrapy.Request):
                detail_fallbacks += 1
                yield item_or_req
            else:
                items_found += 1
                yield item_or_req

        logger.info(
            "Pickaroo listing %s page=%s items=%s detail_fallbacks=%s url=%s",
            location_key,
            page,
            items_found,
            detail_fallbacks,
            response.url,
        )

        if items_found == 0:
            self._empty_pages_by_location[location_key] += 1
        else:
            self._empty_pages_by_location[location_key] = 0

        if (
            self._empty_pages_by_location[location_key]
            >= self.MAX_CONSECUTIVE_EMPTY_PAGES
        ):
            logger.info(
                "Stopping location %s after consecutive empty pages", location_key
            )
            return

        if page < self.MAX_PAGES_PER_LOCATION:
            next_url = self._find_next_page_url(response)
            if next_url:
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_location,
                    meta={
                        "brand_slug": brand_slug,
                        "location_slug": location_slug,
                        "location_key": location_key,
                        "page": page + 1,
                    },
                )

    def parse_product_detail(self, response):
        """Parse product-detail page (fallback)."""
        # Initialize extractor with fallback selectors
        extractor = SelectorExtractor(response, logger)

        # Extract product information using fallback selectors
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        details = extractor.extract("details", self.SELECTORS["details"])

        url = response.url
        category_override = response.meta.get("category")
        if category_override:
            category = category_override
        else:
            breadcrumb = extractor.extract(
                "category", self.SELECTORS["category"], method="getall"
            )
            category = " > ".join(breadcrumb) if breadcrumb else None
        if product_name and price:
            yield {
                "product_name": product_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "details": details,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

    def _root_slug_from_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        return parts[0] if parts else None

    def _is_denied_url(self, url: str) -> bool:
        lowered = url.lower()
        return any(part in lowered for part in self._DENY_PATH_PARTS)

    def _extract_brand_urls(self, response) -> list[str]:
        hrefs = response.css("a::attr(href)").getall()
        out: list[str] = []
        for href in hrefs:
            if not href:
                continue
            if not re.match(r"^/[^/]+/$", href):
                continue
            if self._is_denied_url(href):
                continue
            out.append(urljoin(response.url, href))
        return list(dict.fromkeys(out))

    def _extract_location_urls(
        self, response, brand_slug: str
    ) -> list[tuple[str, str]]:
        hrefs = response.css("a::attr(href)").getall()
        out: list[tuple[str, str]] = []
        prefix = f"/{brand_slug}/products/"
        for href in hrefs:
            if not href:
                continue
            if not href.startswith(prefix):
                continue
            if self._is_denied_url(href):
                continue
            # /{brand}/products/{location}
            parts = [p for p in href.split("/") if p]
            if len(parts) < 3:
                continue
            location_slug = parts[2]
            out.append((urljoin(response.url, href), location_slug))
        return list(dict.fromkeys(out))

    def _extract_listing_products(self, response, category: str):
        links = response.css("a[href*='product-detail/']")
        for link in links:
            href = link.attrib.get("href")
            if not href or self._is_denied_url(href):
                continue
            abs_url = urljoin(response.url, href)

            # Try to pick a reasonable card container around the link.
            card = link.xpath(
                "ancestor::div[contains(@class,'product') or contains(@class,'item')][1]"
            )
            if not card:
                card = link.xpath("ancestor::li[1]")
            context = card[0] if card else link

            product_name = (
                context.css(".product-name::text").get()
                or context.css(".name::text").get()
                or context.css("h3::text").get()
                or context.css("h2::text").get()
                or link.attrib.get("aria-label")
            )
            price_text = (
                context.css("div.price::text").get()
                or context.css("span.price::text").get()
                or context.css("[class*='price']::text").get()
            )

            if product_name and price_text:
                yield {
                    "product_name": product_name.strip(),
                    "category": category,
                    "price": price_text.strip(),
                    "currency": self.currency,
                    "url": abs_url,
                    "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
                }
            else:
                yield scrapy.Request(
                    abs_url,
                    callback=self.parse_product_detail,
                    meta={"category": category},
                )

    def _find_next_page_url(self, response) -> str | None:
        href = (
            response.css("a[rel='next']::attr(href)").get()
            or response.css("a.next::attr(href)").get()
            or response.css("li.pagination-next a::attr(href)").get()
            or response.css("a[class*='next']::attr(href)").get()
        )
        if not href:
            return None
        if self._is_denied_url(href):
            return None
        return urljoin(response.url, href)
