"""
Spider for LuLu Hypermarket Qatar - gcc.luluhypermarket.com (en-qa storefront)

Shared multi-country LuLu GCC storefront (en-ae/en-qa/en-sa/en-om/en-kw/en-bh
locales all live off the same gcc.luluhypermarket.com host per robots.txt --
same pattern as the sibling lulu_om/lulu_kw/lulu_bh/lulu_sa spiders). Category
listing pages are client-rendered (no product data in the raw HTML), but
every PDP is server-rendered with the price and name directly in the markup:
`<span data-testid="price">42.50 QAR</span>` and an `<h1>` name. The page
also carries a schema.org Product JSON-LD block, but its offers.price is
always "0.00"/priceCurrency null regardless of the real price shown in the
HTML -- not usable, so this spider reads the rendered price span instead.

Seeded off /en-qa/sitemap/products-1 (1,980 product URLs at probe time, no
further pagination needed -- a single sitemap file). Verified live
2026-09-01: real, non-zero QAR prices on in-stock items -- Fage Total 0% Fat
Yogurt Lactose Free 450g at 42.50 QAR (matches the sibling countries'
lineup, distinct plausible QAR number). Out-of-stock items render "0.000
QAR" in the same span (confirmed on several cable/electronics PDPs in the
same sitemap sample); those are skipped, not emitted as zero-priced rows.
213 of the 1,980 sitemap URLs match a food/beverage keyword filter
(milk/juice/rice/oil/cheese/coffee/yogurt/etc.) -- a real grocery share.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://gcc.luluhypermarket.com/en-qa/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRICE_RE = re.compile(r'data-testid="price">([\d.]+)\s*QAR')
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_PID_RE = re.compile(r"/p/(\d+)/?$")


class LuluQaSpider(scrapy.Spider):
    name = "lulu_qa"
    allowed_domains = ["luluhypermarket.com"]
    currency = "QAR"
    language = "en"

    custom_settings = {
        # Cloudflare sits in front of gcc.luluhypermarket.com and 403s a
        # plain Scrapy request with no curl_cffi impersonation (same as
        # lulu_om/lulu_kw/lulu_bh). Leave the project-default
        # RandomBrowserMiddleware active by not overriding
        # DOWNLOADER_MIDDLEWARES.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        sub_sitemaps = [u for u in _LOC_RE.findall(response.text) if "/products-" in u]
        logger.info("lulu_qa: %d product sitemap files", len(sub_sitemaps))
        for url in sub_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/p/" in u]
        logger.info("lulu_qa: %d product URLs in %s", len(urls), response.url)
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        price_m = _PRICE_RE.search(response.text)
        if not price_m:
            return
        price = price_m.group(1)
        if float(price) <= 0:
            return
        h1_m = _H1_RE.search(response.text)
        if not h1_m:
            return
        name = html.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1))).strip()
        if not name:
            return
        pid_m = _PID_RE.search(response.url)
        product_id = pid_m.group(1) if pid_m else response.url

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
