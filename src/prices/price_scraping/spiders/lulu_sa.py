"""
Spider for LuLu Hypermarket Saudi Arabia - gcc.luluhypermarket.com (en-sa storefront)

Shared multi-country LuLu GCC storefront (en-ae/en-qa/en-sa/en-om/en-kw/en-bh
locales all live off the same gcc.luluhypermarket.com host per robots.txt --
same pattern as the sibling lulu_kw/lulu_om/lulu_bh spiders). Category listing
pages are client-rendered (no product data in the raw HTML), but every PDP is
server-rendered with the price and name directly in the markup. Unlike the
KWD/OMR/BHD siblings, the en-sa storefront does NOT print the currency code
as text next to the number -- it renders a `pz-icon-saudi-riyal` icon glyph
instead, e.g. `<i class="... pz-icon-saudi-riyal ..."></i><span
data-testid="price">15.95 </span>`. Confirmed live 2026-08-31 on multiple
PDPs (icon class present on every product page checked); currency is
hardcoded to SAR since the page carries no separate ISO code to read. The
schema.org Product JSON-LD block on the page also always reports
offers.price "0.00"/priceCurrency null (same defect as the other GCC
LuLu storefronts) -- not usable, so this spider reads the rendered price
span instead.

Seeded off /en-sa/sitemap/products-1 (1,980 product URLs at probe time, a
single sitemap file, same as en-kw/en-om). Verified live 2026-08-31: real,
non-zero SAR prices on in-stock items (e.g. Dabur Vatika Oil Fusion
Permanent Hair Colour, Intense Red at 15.95 SAR); out-of-stock items render
"0.00 " in the same span (confirmed against "Out of Stock" badge text on a
Party Fusion Birthday Cap PDP) -- those are skipped, not emitted as
zero-priced rows. Grocery/food coverage confirmed substantial: >12% of the
1,980-URL sitemap matches food keywords (cheese, yogurt, pasta, coffee,
meat, etc.) by slug alone, e.g. Fage yogurt, Barilla pasta, Mima Gardens
cheese lines, Torabika coffee.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://gcc.luluhypermarket.com/en-sa/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRICE_RE = re.compile(r'data-testid="price">([\d.]+)\s*<')
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_PID_RE = re.compile(r"/p/([A-Za-z0-9-]+)/?$")


class LuluSaSpider(scrapy.Spider):
    name = "lulu_sa"
    allowed_domains = ["luluhypermarket.com"]
    currency = "SAR"
    language = "en"

    custom_settings = {
        # Cloudflare sits in front of gcc.luluhypermarket.com and 403s a
        # plain Scrapy request with no curl_cffi impersonation (same as
        # lulu_kw/lulu_om/lulu_bh). Leave the project-default
        # RandomBrowserMiddleware active by not overriding
        # DOWNLOADER_MIDDLEWARES. Kept at 1 request/domain: gcc.
        # luluhypermarket.com is a shared regional platform and the Kuwait
        # lulu_kw sibling may be scraping the same host concurrently.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        sub_sitemaps = [u for u in _LOC_RE.findall(response.text) if "/products-" in u]
        logger.info("lulu_sa: %d product sitemap files", len(sub_sitemaps))
        for url in sub_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/p/" in u]
        logger.info("lulu_sa: %d product URLs in %s", len(urls), response.url)
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
