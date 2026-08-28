"""
Spider for Jarir Bookstore Kuwait - jarir.com (kw-en storefront)

Same Vue-SSR/Magento-style backend as jarir_sa (see that spider's docstring
for the platform details). The Kuwait storefront's own sitemap
(sitemap_kw_ar.xml) does not serve valid XML (returns a binary image
payload, same defect as the UAE/Qatar storefronts), so this spider reuses
the Saudi Arabia product-sitemap index for URL discovery and re-requests
each slug under the /kw-en/ prefix. Verified live: /kw-en/ PDPs return a
real, independently-priced schema.org Product block in KWD (e.g. SKU 27177
prices at 6.90 KWD vs 89.00 QAR / 8.69 BHD on the sibling storefronts) — a
genuine Kuwait storefront, not a fallback. KWD is a 3-decimal-place
currency; the JSON-LD price is already a plain decimal string as rendered
(not an integer minor-unit value), so no rescaling is needed. Not every
SA-catalog slug is stocked in the Kuwait storefront; parse_product silently
skips PDPs with no price or an out-of-stock/zero price, same as
jarir_sa/jarir_ae/jarir_qa.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.jarir.com/media/sitemap/sitemap_sa_ar.xml"
_LOCALE_PREFIX = "kw-en"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class JarirKwSpider(scrapy.Spider):
    name = "jarir_kw"
    allowed_domains = ["jarir.com"]
    currency = "KWD"
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
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        sub_sitemaps = [u for u in _LOC_RE.findall(response.text) if "_product_" in u]
        logger.info("jarir_kw: %d product sitemap files", len(sub_sitemaps))
        for url in sub_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info("jarir_kw: %d product URLs in %s", len(urls), response.url)
        for url in urls:
            slug = url.rsplit("/", 1)[-1]
            pdp_url = f"https://www.jarir.com/{_LOCALE_PREFIX}/{slug}"
            yield scrapy.Request(pdp_url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            for node in self._iter_nodes(data):
                if isinstance(node, dict) and node.get("@type") == "Product":
                    product = node
                    break
            if product:
                break
        if not product:
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", "0", "0.00"):
            return

        yield {
            "product_id": product.get("sku") or response.url,
            "product_name": str(name)[:500],
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "category": product.get("category"),
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
