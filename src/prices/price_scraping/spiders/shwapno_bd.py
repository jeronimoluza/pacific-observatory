"""
Spider for Shwapno (ACI) (Bangladesh) — https://www.shwapno.com/.

React Server Components (Next.js app router) storefront. Category listing
pages do not server-render product cards (client-fetched), but the sitemap
gives a full URL enumeration: /sitemap.xml -> sitemap-products.xml -> 22
numbered sub-sitemaps (sitemap-products-1.xml .. -22.xml), each ~1,000+
product PDP URLs, e.g. 'emami-7-oils-in-one-pumpkin-plus-hair-oil-200ml'.

Each PDP embeds a schema.org Product JSON-LD block inside a React-flight
streaming chunk (`self.__next_f.push([1,"..."])`), not a plain
`<script type="application/ld+json">` tag — the escaped string has to be
unescaped before regexing it out. Re-verified live 2026-08-06: GET
/7up-pet-bottle-2-25ltr- -> 200, h1 '7Up 1.75Ltr. (Pet Bottle)', JSON-LD
offers.price=140 offers.priceCurrency=BDT sku=2303753.

Full-catalog walk = sitemap crawl (22 sub-sitemaps) + one PDP fetch per
product URL. No auth, no WAF observed.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.shwapno.com"
_SITEMAP_INDEX = f"{_BASE}/sitemap-products.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_FLIGHT_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
_H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")
_OFFERS_RE = re.compile(
    r'"sku":"([^"]*)".*?"offers":\{"@type":"Offer","priceCurrency":"([A-Z]{3})",'
    r'"price":([0-9.]+)',
    re.S,
)


class ShwapnoBdSpider(scrapy.Spider):
    name = "shwapno_bd"
    allowed_domains = ["shwapno.com"]
    currency = "BDT"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
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
        sub_sitemaps = _LOC_RE.findall(response.text)
        logger.info(f"shwapno_bd: {len(sub_sitemaps)} sub-sitemaps")
        for url in sub_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sub_sitemap)

    def parse_sub_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"shwapno_bd: {response.url} -> {len(urls)} products")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_pdp)

    def parse_pdp(self, response):
        h1_match = _H1_RE.search(response.text)
        name = html.unescape(h1_match.group(1)).strip() if h1_match else None

        flight_chunks = _FLIGHT_RE.findall(response.text)
        blob = "".join(flight_chunks).encode().decode("unicode_escape", errors="ignore")
        m = _OFFERS_RE.search(blob)
        if not name or not m:
            return
        sku, currency, price = m.groups()
        yield {
            "product_id": sku or response.url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": name[:500],
            "category": None,
            "price": price,
            "currency": currency or self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
