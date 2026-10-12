"""
Spider for Pepia4Home (Aruba) - pepia4home.com

Wix store (wine and spirits distributor, Oranjestad). The Wix product sitemap lists
every /product-page/<slug> URL; each PDP carries a Schema.org Product JSON-LD block
with name, offers.price and offers.priceCurrency (AWG). Page family: PDP.
"""

import json
import logging
from datetime import datetime, timezone

from scrapy.spiders import SitemapSpider

logger = logging.getLogger(__name__)


class Pepia4homeAwSpider(SitemapSpider):
    name = "pepia4home_aw"
    allowed_domains = ["www.pepia4home.com", "pepia4home.com"]
    sitemap_urls = ["https://www.pepia4home.com/store-products-sitemap.xml"]
    sitemap_rules = [(r"/product-page/", "parse_product")]
    currency = "AWG"

    custom_settings = {"DOWNLOAD_DELAY": 1, "CONCURRENT_REQUESTS": 1}

    def parse_product(self, response):
        product = None
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            for node in data if isinstance(data, list) else [data]:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    product = node
                    break
            if product:
                break
        if not product:
            logger.warning("No Product JSON-LD at %s", response.url)
            return
        offer = product.get("offers") or product.get("Offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        name = product.get("name")
        if price in (None, "") or not name:
            logger.warning("Missing price or name at %s", response.url)
            return
        yield {
            "product_id": product.get("sku") or response.url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": str(name).strip()[:500],
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "category": None,
            "url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
