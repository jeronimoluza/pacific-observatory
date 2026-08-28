"""
Spider for 173 Brunei (Brunei) - www.173brunei.com

EasyStore platform (Southeast Asian Shopify-alike SaaS). The
/collections/all listing pages are server-rendered with name + price
inline on each product card - no PDP visits needed. Price sits in
span.money[data-ori-price] as a clean decimal string (avoids parsing the
"B$" display prefix). Paginates via ?limit=50&page=N.
"""

import logging
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)


class Brunei173Spider(scrapy.Spider):
    name = "173brunei"
    allowed_domains = ["173brunei.com", "www.173brunei.com"]
    currency = "BND"
    language = "en"

    SELECTORS = {
        "products": "div.product_grid-item",
        "product_name": "p.grid-link__title::text",
        "price": "span.money::attr(data-ori-price)",
        "link": "a.product-meta_link::attr(href)",
        "product_id": "div.addToCartList::attr(data-product-id)",
        "next_page": 'ul.pagination-custom li a[title="Next"]::attr(href)',
    }

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 3,
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.173brunei.com/collections/all?limit=50",
            callback=self.parse_listing,
        )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()

        for product in response.css(self.SELECTORS["products"]):
            name = product.css(self.SELECTORS["product_name"]).get()
            price = product.css(self.SELECTORS["price"]).get()
            if not name or not price:
                logger.debug(f"missing name/price on card at {response.url}")
                continue

            href = product.css(self.SELECTORS["link"]).get() or ""
            product_id = product.css(self.SELECTORS["product_id"]).get()

            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": None,
                "price": price.strip(),
                "currency": self.currency,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        next_href = response.css(self.SELECTORS["next_page"]).get()
        if next_href:
            yield scrapy.Request(
                response.urljoin(next_href),
                callback=self.parse_listing,
            )

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Archived
    # snapshots of this EasyStore theme are PDP pages under
    # /collections/all/products/<slug>, not the listing pages the live
    # crawl walks. The theme injects schema.org JSON-LD client-side via JS
    # (no static <script type="application/ld+json"> in the raw HTML), but
    # OpenGraph tags -- og:title, og:price:amount, og:price:currency -- are
    # server-rendered and carry the same data, so the shared meta tier is
    # sufficient on its own here.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived 173 Brunei PDP page (EasyStore theme)."""
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row
