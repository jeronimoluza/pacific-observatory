"""
Spider for Butlon (Netherlands) — https://www.butlon.com/.

Anti-foodwaste / bulk-buying online supermarket (short-THT deals, surplus
stock). Next.js storefront, but fully enumerable without hydration: the
site's own `/sitemap.xml` lists every product-detail URL directly under
`/p/<slug>` (1,439 of them live, 2026-09-06), so this walks the sitemap
rather than crawling categories.

Each PDP is server-rendered with a `schema.org/Product` JSON-LD block
carrying `sku`, `offers.price`, `offers.priceCurrency`, and a separate
`BreadcrumbList` JSON-LD block whose last item is the category label.
Sample verified live: "Appelsientje Kids fruitdrink framboos 6-pack"
sku=238160, EUR 2.49 (discounted from a 3.49 strikethrough), category
"Frisdrank & Water".
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.butlon.com/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
MAX_PRODUCTS = 5000  # safety cap, above the ~1.4k observed catalog size


class ButlonComSpider(scrapy.Spider):
    name = "butlon_com"
    allowed_domains = ["butlon.com"]
    currency = "EUR"
    language = "nl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        product_urls = [loc for loc in locs if "/p/" in loc]
        logger.info("butlon_com: sitemap lists %d product URLs", len(product_urls))
        for url in product_urls[:MAX_PRODUCTS]:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        category = None
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            if data.get("@type") == "Product":
                product = data
            elif data.get("@type") == "BreadcrumbList":
                items = data.get("itemListElement", [])
                # Last item is the PDP itself (name == product name); the
                # category is the second-to-last crumb.
                if len(items) >= 2:
                    category = items[-2].get("name")

        if not product:
            logger.warning("butlon_com: no Product JSON-LD on %s", response.url)
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": product.get("sku") or product.get("gtin13") or response.url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in (offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
