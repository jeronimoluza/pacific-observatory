"""
Embassy Liquor Store -- https://www.embassyliquorstore.com/ (Windhoek,
Namibia -- wines, beers, spirits, cigars).

Wix Stores site (confirmed via the Wix-generated /sitemap.xml ->
store-products-sitemap.xml chain; not an Ecwid app despite marketing copy
mentioning Ecwid elsewhere on the page -- that text is unrelated site
content, not the actual storefront engine). Server-rendered PDP HTML
carries a standard schema.org JSON-LD Product block with an explicit
`offers.priceCurrency: "NAD"` -- Tier 1A, no Playwright needed.

Sitemap (https://www.embassyliquorstore.com/store-products-sitemap.xml)
lists 448 product URLs under /product-page/<slug> as of 2026-09-11 --
this is the enumeration mechanism (no category/listing pagination is
crawled; each sitemap URL is fetched directly for its own JSON-LD).

Division 02 (alcohol) coverage: Namibia currently has no dedicated
alcohol retailer source (doorstep_na is a mixed convenience/alcohol
delivery app, not liquor-specific) -- this fills that gap directly.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.embassyliquorstore.com/store-products-sitemap.xml"


class EmbassyliquorNaSpider(scrapy.Spider):
    name = "embassyliquor_na"
    allowed_domains = ["embassyliquorstore.com"]
    currency = "NAD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = response.xpath(
            "//*[local-name()='loc']/text()"
        ).getall()
        logger.info("embassyliquor_na: %s product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url.strip(), callback=self.parse_product)

    def parse_product(self, response):
        for script in response.css(
            'script[type="application/ld+json"]::text'
        ).getall():
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
        logger.warning(
            "embassyliquor_na: no Product JSON-LD found at %s", response.url
        )

    def _item(self, node: dict, url: str):
        offers = node.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            return None

        price = offers.get("price")
        if price is None:
            return None
        try:
            if float(price) <= 0:
                return None
        except (TypeError, ValueError):
            return None

        name = str(node.get("name") or "").strip()
        name = re.sub(r"\s+", " ", name)
        if not name:
            return None

        currency = offers.get("priceCurrency") or self.currency
        availability = str(offers.get("availability") or "")
        available = "instock" in availability.lower() or "outofstock" not in availability.lower()

        return {
            "product_id": node.get("sku"),
            "product_name": name[:500],
            "category": node.get("category"),
            "price": str(price),
            "currency": currency,
            "available": available,
            "url": offers.get("url") or url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
