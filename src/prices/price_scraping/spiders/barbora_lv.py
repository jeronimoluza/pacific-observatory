"""
Spider for Barbora (Latvia) — https://barbora.lv.

Same platform and same two-hop harvest as barbora_ee (see that file for
full rationale) — Constructor.io public search key embedded in the
homepage (`key_Ud2GfuuTdK6bx4xS`) resolves search terms to product
slugs, then each product's own page is SSR with price in a
`"units":[{"id":0,"price":N.NN,...}]` block. Re-verified live
2026-08-06: GET https://ac.cnstrc.com/search/piens?key=key_Ud2GfuuTdK6bx4xS
-> HTTP 200, 2,050 hits; GET
https://barbora.lv/produkti/piens-tere-2-5-proc-1-5-l -> HTTP 200, price
1.37 EUR. Not code-shared with barbora_ee (per-country Constructor.io
key + product URL prefix differ: /produkti/ here vs /toode/ on .ee) to
keep each file self-contained and under the line cap.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://ac.cnstrc.com/search/{term}"
_CIO_KEY = "key_Ud2GfuuTdK6bx4xS"
_PRODUCT_BASE = "https://barbora.lv/produkti/"
_PRICE_RE = re.compile(r'"units":\[\{"id":0,"price":([\d.]+)')
_TITLE_RE = re.compile(r"<title>([^<]+)</title>")

_SEARCH_TERMS = [
    "piens",
    "maize",
    "siers",
    "olas",
    "gaļa",
    "vista",
    "zivis",
    "jogurts",
    "sviests",
    "cukurs",
    "milti",
    "rīsi",
    "makaroni",
    "kafija",
    "tēja",
    "sula",
    "ūdens",
    "alus",
    "vīns",
    "šokolāde",
    "cepumi",
    "konservi",
    "dārzeņi",
    "augļi",
    "desa",
]
_RESULTS_PER_TERM = 20


class BarboraLvSpider(scrapy.Spider):
    name = "barbora_lv"
    allowed_domains = ["barbora.lv", "cnstrc.com"]
    currency = "EUR"
    language = "lv"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for term in _SEARCH_TERMS:
            yield scrapy.Request(
                _SEARCH_URL.format(term=term)
                + f"?key={_CIO_KEY}&num_results_per_page={_RESULTS_PER_TERM}",
                callback=self.parse_search,
            )

    def parse_search(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        results = (data.get("response") or {}).get("results") or []
        for r in results:
            slug = (r.get("data") or {}).get("url")
            if not slug:
                continue
            yield scrapy.Request(
                f"{_PRODUCT_BASE}{slug}",
                callback=self.parse_product,
                meta={"slug": slug},
            )

    def parse_product(self, response):
        price_m = _PRICE_RE.search(response.text)
        title_m = _TITLE_RE.search(response.text)
        if not price_m or not title_m:
            return
        name = html.unescape(title_m.group(1).split(" | ")[0].strip())
        if not name:
            return
        slug = response.meta["slug"]
        yield {
            "product_id": slug,
            "product_name": name[:500],
            "category": None,
            "price": price_m.group(1),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
