"""
KAL (Togo) — https://www.kal-app.com/.

Lome delivery super-app (express/restaurants/courses/pharmacie/boutiques
verticals) built on Next.js. The client-rendered listing pages
(/products, /partners/<slug>) only server-render a capped first slice of
cards, but every individual product page is server-rendered with a full
schema.org Product JSON-LD block (name, sku, brand, offers.price,
offers.priceCurrency, offers.availability, shippingDestination.
addressCountry="TG") baked into the raw HTML — confirmed live 2026-08-31,
no JS execution needed (Tier 1A).

/sitemap.xml is the product-URL seed: 125 distinct
/partners/<slug>/products/<id> URLs across 44 Lome vendors (electronics,
restaurants, beauty, boutiques) as of this run. Each partner's own
`LocalBusiness` JSON-LD block confirms Lome/Togo (areaServed lists Lome,
Sokode, Kara, etc., addressCountry "TG"), so this is a Togo-priced,
Togo-located marketplace, not a diaspora storefront.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kal-app.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
_PRODUCT_ID_RE = re.compile(r"/partners/([^/]+)/products/([^/?#]+)")


class KalTgSpider(scrapy.Spider):
    name = "kal_tg"
    allowed_domains = ["kal-app.com"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_URL, callback=self.parse_sitemap, errback=self.errback
        )

    def parse_sitemap(self, response):
        urls = set(response.xpath("//*[local-name()='loc']/text()").getall())
        product_urls = sorted(u for u in urls if _PRODUCT_ID_RE.search(u))
        logger.info(
            f"{self.name}: sitemap urls={len(urls)} product_urls={len(product_urls)}"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script)
            except (json.JSONDecodeError, TypeError):
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    item = self._item(node, response.url)
                    if item:
                        yield item
                    return
        logger.warning(f"{self.name}: no Product JSON-LD at {response.url}")

    def _item(self, node: dict, url: str):
        name = node.get("name")
        offers = node.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        if not name or price is None:
            return None
        brand = node.get("brand") or {}
        category = brand.get("name") if isinstance(brand, dict) else None
        availability = str(offers.get("availability") or "").lower()
        return {
            "product_id": str(node.get("sku") or ""),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "outofstock" not in availability,
            "url": offers.get("url") or url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
