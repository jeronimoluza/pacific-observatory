"""
Spider for Frisco.pl (Poland) — https://www.frisco.pl/.

React-based online supermarket. Category/search-results pages
(/c,<id>/cat,<slug>/stn,searchResults) are client-hydrated with zero product
data in the raw response -- confirmed empty via curl (0 price occurrences,
0 product-name occurrences). Individual product pages, however, ARE
server-rendered with schema.org Product/Offer microdata, and the full
product catalog is enumerable via the site's own product sitemap
(13 shards, ~1,000 <loc> entries each, ~13.7k products total per
sitemap-index.xml). So the walk here is: sitemap shards -> product detail
pages (SSR), not category pagination.

Re-verified live 2026-08-06: GET /sitemap-index.xml -> 200, lists
sitemap-products-{1..13}-of-13.xml. One product detail page, e.g.
/pid,88437/n,felix-party-mix-przekaska-dla-kotow-o-smaku-kurczaka-watrobki-i-indyka/stn,product
-> 200, 1.49MB SSR HTML with:
  <h1 class="title ...">FELIX® Party MIX Przekąska dla kotów...</h1>
  <meta itemProp="price" content="5.99"/>
  <meta itemProp="priceCurrency" content="PLN"/>
  <meta itemProp="availability" content="https://schema.org/InStock"/>
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.frisco.pl"
_SITEMAP_INDEX = f"{_BASE}/sitemap-index.xml"
MAX_PRODUCTS = 20000  # safety cap, above the ~13.7k observed catalog size

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PID_RE = re.compile(r"/pid,(\d+)/")
_H1_RE = re.compile(r'<h1[^>]*class="title[^"]*">([^<]+)</h1>')
_PRICE_RE = re.compile(r'itemProp="price" content="([0-9.]+)"')
_CURRENCY_RE = re.compile(r'itemProp="priceCurrency" content="([A-Z]{3})"')
_AVAIL_RE = re.compile(r'itemProp="availability" content="[^"]*?(InStock|OutOfStock)"')


class FriscoPlSpider(scrapy.Spider):
    name = "frisco_pl"
    allowed_domains = ["frisco.pl", "www.frisco.pl"]
    currency = "PLN"
    language = "pl"

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
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        for loc in _LOC_RE.findall(response.text):
            if "sitemap-products-" in loc:
                yield scrapy.Request(loc, callback=self.parse_product_shard)

    def parse_product_shard(self, response):
        for loc in _LOC_RE.findall(response.text):
            yield scrapy.Request(loc, callback=self.parse_product, meta={"url": loc})

    def parse_product(self, response):
        if response.meta.get("count", 0) >= MAX_PRODUCTS:
            return
        pid_match = _PID_RE.search(response.url)
        h1_match = _H1_RE.search(response.text)
        price_match = _PRICE_RE.search(response.text)
        if not (pid_match and h1_match and price_match):
            logger.warning(f"frisco_pl: incomplete product page {response.url}")
            return
        currency_match = _CURRENCY_RE.search(response.text)
        avail_match = _AVAIL_RE.search(response.text)
        yield {
            "product_id": pid_match.group(1),
            "product_name": h1_match.group(1).strip()[:500],
            "category": None,
            "price": price_match.group(1),
            "currency": currency_match.group(1) if currency_match else self.currency,
            "available": (avail_match.group(1) == "InStock") if avail_match else True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
