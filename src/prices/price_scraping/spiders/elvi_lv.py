"""
Spider for Elvi (Latvia) — https://elvi.lv/.

Bespoke WordPress storefront (custom "produkti" post type). There is no
category-listing catalog to walk: the sitemap (https://elvi.lv/sitemap.xml)
is the only enumeration surface, and it lists ~2870 individual
/produkti/<slug>/ product pages directly (confirmed live 2026-08-06). Each
product page is plain SSR HTML: e.g. /produkti/banani-17/ -> 200, <h1>BANĀNI
</h1>, price block `<div class="price default">...<p ...>0.89€</p></div>`,
category breadcrumb `<a class="product-term" href="...">Augļi un dārzeņi</a>`.

We fetch the sitemap once, filter to /produkti/ URLs, then walk every
product page (whole-catalog walk via the site's only enumeration surface).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://elvi.lv/sitemap.xml"
_LOC_RE = re.compile(r"<loc>(https://elvi\.lv/produkti/[^<]+)</loc>")
_PRICE_RE = re.compile(
    r'class="price default">.*?<p[^>]*>([0-9]+\.[0-9]{2})€</p>', re.S
)
_TITLE_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")
_CATEGORY_RE = re.compile(r'class="product-term" href="[^"]*">([^<]+)</a>')
MAX_PRODUCTS = 5000  # safety cap, above the ~2870 observed catalog size


class ElviLvSpider(scrapy.Spider):
    name = "elvi_lv"
    allowed_domains = ["elvi.lv"]
    currency = "EUR"
    language = "lv"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"elvi_lv: sitemap product urls={len(urls)}")
        for url in urls[:MAX_PRODUCTS]:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        title_m = _TITLE_RE.search(response.text)
        price_m = _PRICE_RE.search(response.text)
        if not title_m or not price_m:
            return
        cat_m = _CATEGORY_RE.search(response.text)
        yield {
            "product_id": response.url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": html.unescape(title_m.group(1)).strip()[:500],
            "category": html.unescape(cat_m.group(1)).strip() if cat_m else None,
            "price": price_m.group(1),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
