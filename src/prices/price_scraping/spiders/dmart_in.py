"""
DMart Ready (India) — https://www.dmart.in/.

Next.js (App Router) storefront for Avenue E-Commerce Ltd's online grocery
arm. The homepage ships no useful client API surface (no window.__NEXT_DATA__,
route-specific chunks are code-split so the PLP/PDP fetch calls aren't in the
initially-loaded bundles), but the site publishes a real sitemap:

    /sitemap.xml -> /sitemap/products.xml -> products_1.xml, products_2.xml
    (~37,500 product URLs total, no pagination cap)

Each product page is server-rendered by the Next.js App Router and streams a
React Server Component payload as a sequence of
`<script>self.__next_f.push([1, "..."])</script>` chunks. The chunk that
carries the product-level object contains the fields we need, but EVERY
quote inside it is backslash-escaped on the wire (it is a JS string literal
inside the push() call), so the raw response body reads:

    \"name\":\"Britannia Good Day Cashew Cookies : 52.5 g\",\"skuUniqueID\":\"1362502\",
    \"articleNumber\":\"120006587\", ... ,\"priceMRP\":\"10.00\",\"priceSALE\":\"9.00\", ...

and, earlier in the same page, the category:

    \"categoryId\":\"93195\",\"categoryName\":\"Packaged Food\"

(all needed key:value pairs land inside a single chunk, never split across
the streaming boundary). The parser normalizes by replacing the literal
two-character sequence `\"` with `"` once per page before running the field
regexes below — trying to match the escaped form directly was the first
thing tried and it silently matched nothing on every page.

No pincode/store selection is required to see a price — the page serves a
default MRP-anchored price to anonymous requests, so plain HTTP works. This
is Tier 1A (regex over raw HTML); there is no clean CSS selector because the
values live inside a JS string literal, not the DOM.

Prices are INR (site is India-only, ₹ symbol throughout); no explicit
currency field is emitted by the page, so it is set at the class level.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dmart.in"
SITEMAP_INDEX = f"{BASE_URL}/sitemap/products.xml"

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NAME_SKU_RE = re.compile(r'"name":"((?:[^"\\]|\\.)*)","skuUniqueID":"(\d+)"')
_PRICE_RE = re.compile(r'"priceMRP":"([\d.]+)","priceSALE":"([\d.]+)"')
_CATEGORY_RE = re.compile(r'"categoryName":"((?:[^"\\]|\\.)*)"')
_ARTICLE_RE = re.compile(r'"articleNumber":"(\d+)"')


class DmartInSpider(scrapy.Spider):
    name = "dmart_in"
    allowed_domains = ["dmart.in"]
    currency = "INR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 6,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_INDEX, callback=self.parse_sitemap_index, errback=self.errback
        )

    def parse_sitemap_index(self, response):
        sub_sitemaps = _LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(sub_sitemaps)} product sitemap file(s)")
        for loc in sub_sitemaps:
            yield scrapy.Request(
                loc, callback=self.parse_product_sitemap, errback=self.errback
            )

    def parse_product_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        # The RSC stream escapes every quote in the embedded product JSON
        # (`\"key\":\"value\"`); normalize once so the plain-quote regexes
        # below match. See module docstring.
        text = response.text.replace('\\"', '"')

        name_sku = _NAME_SKU_RE.search(text)
        price = _PRICE_RE.search(text)
        if not name_sku or not price:
            logger.warning(
                f"{self.name}: could not extract product data from {response.url}"
            )
            return

        sale_price = price.group(2)
        try:
            if float(sale_price) <= 0:
                return
        except ValueError:
            return

        name = name_sku.group(1).encode().decode("unicode_escape")
        sku_id = name_sku.group(2)

        article = _ARTICLE_RE.search(text)
        category_match = _CATEGORY_RE.search(text)
        category = (
            category_match.group(1).encode().decode("unicode_escape")
            if category_match
            else None
        )

        yield {
            "product_id": article.group(1) if article else sku_id,
            "product_name": name[:500],
            "category": category,
            "price": sale_price,
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
