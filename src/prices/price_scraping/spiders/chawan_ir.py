"""
Chawan (chawan.ir) — Iranian personal-care/hygiene drugstore retailer.

Category URLs discovered via /sitemap.xml (~1,095 /shop/<id>-<slug>/
entries; no dedicated product sitemap on this platform). Each category
page embeds a Schema.org ItemList JSON-LD block directly in the
server-rendered HTML, one ListItem per product tile, each carrying its
own offers.price/priceCurrency -- no need to fetch individual product
pages. Verified live 2026-08-18: priceCurrency is "IRR" already (not
Toman) -- no unit conversion needed. Pagination via ?page=N confirmed
enumerable: page 1 vs page 2 of the same category returned 20/20 disjoint
product URLs. WooCommerce Store API 404s on this domain (not a Woo
store); the platform's own JS globals name a
site_api_url=/api/ and shop_recent_api_url=/api/shop/product/catalog/
but the embedded ItemList already gives clean structured data without
touching those endpoints.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://chawan.ir/sitemap.xml"
MAX_PAGES = 20
_ITEMLIST_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)


class ChawanIrSpider(scrapy.Spider):
    name = "chawan_ir"
    allowed_domains = ["chawan.ir"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_URL,
            callback=self.parse_sitemap,
            errback=self.errback,
        )

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        category_urls = [u for u in urls if "/shop/" in u]
        logger.info(
            f"sitemap: {len(urls)} urls total, queued {len(category_urls)} categories"
        )
        for url in category_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"page": 1},
            )

    def parse_listing(self, response):
        page = response.meta["page"]
        items = self._extract_item_list(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for entry in items:
            row = self._parse_entry(entry, scraped_at)
            if row is not None:
                n += 1
                yield row
        logger.info(f"chawan_ir: {response.url} page={page} items={n}")

        if n > 0 and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in response.url else "?"
            yield scrapy.Request(
                f"{response.url}{sep}page={nxt}",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"page": nxt},
            )

    def _extract_item_list(self, body: str) -> list:
        for block in _ITEMLIST_RE.findall(body):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                return data.get("itemListElement", [])
        return []

    def _parse_entry(self, entry: dict, scraped_at: str) -> dict | None:
        item = entry.get("item") if isinstance(entry, dict) else None
        if not isinstance(item, dict):
            return None
        name = item.get("name")
        offer = item.get("offers") or {}
        price = offer.get("price")
        url = item.get("url")
        if not (name and price and url):
            return None
        category = item.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        return {
            "product_id": url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
