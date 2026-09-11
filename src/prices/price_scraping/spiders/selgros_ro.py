"""
Selgros Romania -- https://www.selgros.ro/, a cash & carry wholesaler
(Transgourmet group). channel=wholesale: this is a members-only bulk-buying
chain (restaurants, small retailers), not a consumer supermarket, and its
own JSON-LD prices are genuinely tiered by purchase quantity.

The corporate domain www.selgros.ro is Drupal (`Simple XML Sitemap` module)
and its own `/sitemap.xml` (845 URLs) and `shop.selgros.ro/sitemap.xml` (12
URLs) are content/landing pages only -- NOT the product catalog, despite
both looking like plausible catalog domains. The real catalog sitemap is
named directly in `robots.txt`:
`Sitemap: https://www.selgros.ro/sites/default/files/sitemaps/products-index.xml`
-- a genuine `<sitemapindex>` of 2 shards, `products-1.xml` (10,000 URLs)
and `products-2.xml` (6,129 URLs), 16,129 total, ZERO overlap between the
two shards (verified live 2026-09-10). Every URL sits under
`/exploreaza-sortimentul-selgros/product/<slug>-<id>`.

Each PDP embeds a Schema.org Product JSON-LD node whose `offers` is a LIST,
not a single dict: Selgros publishes one Offer per (store x quantity-tier)
combination -- e.g. one product carried 72 offers across 24 stores x 3 tiers
(base price, and 2 bulk-discount tiers keyed by `eligibleQuantity.minValue`).
Verified live on 5 URLs (2 shards): all RON, e.g. "IGIENOL DEZINFECTANT
MARIN 750ML" RON 15.29 (base/no minValue), "BIC TEXTMARKER SET 5 CULORI" RON
7.01. This spider records the single-unit ("walk-in", no `eligibleQuantity`)
price from the FIRST such offer in document order as the product's price --
a deterministic but somewhat arbitrary choice of "which of 24 stores" to
represent nationally; store-level and bulk-tier granularity is discarded.
Falls back to the cheapest available offer if every offer on a page carries
a minimum quantity.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_INDEX = (
    "https://www.selgros.ro/sites/default/files/sitemaps/products-index.xml"
)


class SelgrosRoSpider(scrapy.Spider):
    name = "selgros_ro"
    allowed_domains = ["selgros.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(SITEMAP_INDEX, callback=self.parse_index)

    def parse_index(self, response):
        shard_urls = response.xpath("//*[local-name()='loc']/text()").getall()
        logger.info(f"selgros_ro: {len(shard_urls)} product-sitemap shards")
        for url in shard_urls:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        logger.info(f"selgros_ro: shard {response.url} -> {len(urls)} product urls")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            return
        name = product.get("name")
        offers = product.get("offers")
        if isinstance(offers, dict):
            offers = [offers]
        if not isinstance(offers, list) or not offers:
            return

        offer = self._pick_offer(offers)
        if offer is None:
            return
        try:
            price = float(offer.get("price"))
        except (TypeError, ValueError):
            return
        if not name or price <= 0:
            return
        currency = offer.get("priceCurrency") or self.currency

        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "category": offer.get("category"),
            "price": str(price),
            "currency": currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _pick_offer(offers: list) -> dict | None:
        """Prefer the single-unit ("walk-in") price over a bulk-quantity tier."""
        walk_in = [o for o in offers if isinstance(o, dict) and "eligibleQuantity" not in o]
        pool = walk_in or [o for o in offers if isinstance(o, dict)]
        if not pool:
            return None

        def _price(o):
            try:
                return float(o.get("price"))
            except (TypeError, ValueError):
                return float("inf")

        return pool[0] if walk_in else min(pool, key=_price)

    @staticmethod
    def _extract_product(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None
