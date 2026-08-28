"""
Spider for Jarir Bookstore Qatar - jarir.com (qa-en storefront)

Same Vue-SSR/Magento-style backend as jarir_sa (see that spider's docstring
for the platform details). The Qatar storefront's own sitemap
(sitemap_qa_ar.xml) does not serve valid XML (returns a binary image
payload, same defect as the UAE storefront), so this spider reuses the
Saudi Arabia product-sitemap index for URL discovery and re-requests each
slug under the /qa-en/ prefix. Verified live: /qa-en/ PDPs return a real,
independently-priced schema.org Product block in QAR (e.g. SKU 27177 prices
at 89.00 QAR vs 6.90 KWD / 8.69 BHD on the sibling storefronts) — a genuine
Qatar storefront, not a fallback. Not every SA-catalog slug is stocked in
the Qatar storefront; parse_product silently skips PDPs with no price or an
out-of-stock/zero price, same as jarir_sa/jarir_ae.

Note: the equivalent /om-en/ prefix does NOT resolve to a real Oman
storefront (it silently falls back to the Arabic Saudi PDP with SAR
pricing) — Jarir has no live Oman storefront, so no jarir_om spider exists.

Sitemap URLs are shuffled per-file before requesting (see parse_sitemap):
sitemap_sa_ar_product_1.xml is one large contiguous block of Arabic-book
SKUs that Qatar does not stock at all, and without shuffling a capped smoke
run can exhaust its whole request budget on that one unstocked category and
report a false zero.
"""

import json
import logging
import random
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.jarir.com/media/sitemap/sitemap_sa_ar.xml"
_LOCALE_PREFIX = "qa-en"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class JarirQaSpider(scrapy.Spider):
    name = "jarir_qa"
    allowed_domains = ["jarir.com"]
    currency = "QAR"
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
        logger.info("jarir_qa: %d product sitemap files", len(sub_sitemaps))
        for url in sub_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info("jarir_qa: %d product URLs in %s", len(urls), response.url)
        # sitemap_sa_ar_product_1.xml is one large contiguous block of
        # Arabic-book SKU IDs that Qatar's storefront does not stock at all
        # (verified: a max-items=20 smoke run crawled 342 consecutive
        # arabic-books PDPs with zero yield before closespider_timeout_no_item
        # fired). Shuffle so the request queue isn't dominated by that one
        # unstocked category — other slugs (electronics, toys, stationery)
        # are confirmed stocked and priced in QAR.
        random.shuffle(urls)
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
