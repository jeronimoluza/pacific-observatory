"""
Spider for Drakes Supermarkets (Australia) - online.drakes.com.au

Largest independent AU grocer. The online store is a per-store "Shopfront"
(Marketplacer) app served on numbered store subdomains (e.g. 087 = Drakes
McDowall). The browse grid hydrates client-side, but every product ("line")
page is server-rendered with a schema.org Product JSON-LD block carrying name +
offers.price + priceCurrency, and a BreadcrumbList JSON-LD for the category.

We seed off the store subdomain's sitemap.xml (~14.8k /lines/ URLs) and parse
each PDP's JSON-LD. Plain requests work (200 with a browser UA); no Playwright,
no impersonation. Prices are that store's; 087 is used as the representative
store for the chain.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_STORE = "087"
_BASE = f"https://{_STORE}.drakes.com.au"
_SITEMAP = f"{_BASE}/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class DrakesSupermarketsSpider(scrapy.Spider):
    name = "drakes_supermarkets"
    allowed_domains = ["drakes.com.au"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/lines/" in u]
        logger.info("drakes_supermarkets: %d product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        breadcrumb = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            for node in self._iter_nodes(data):
                if not isinstance(node, dict):
                    continue
                t = node.get("@type")
                if t == "Product" and product is None:
                    product = node
                elif t == "BreadcrumbList" and breadcrumb is None:
                    breadcrumb = node
        if not product:
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", "0", "0.00"):
            return

        slug = response.url.rstrip("/").rsplit("/lines/", 1)[-1]
        yield {
            "product_id": slug,
            "product_name": str(name)[:500],
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "category": self._category(breadcrumb),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _iter_nodes(data):
        if isinstance(data, list):
            for d in data:
                yield d
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                for d in graph:
                    yield d
            else:
                yield data

    @staticmethod
    def _category(breadcrumb):
        if not breadcrumb:
            return None
        items = breadcrumb.get("itemListElement") or []
        names = []
        for i in items:
            if not isinstance(i, dict):
                continue
            n = (
                (i.get("item") or {}).get("name")
                if isinstance(i.get("item"), dict)
                else i.get("name")
            )
            if n and n != "Home":
                names.append(n)
        return " > ".join(names[:4]) if names else None
