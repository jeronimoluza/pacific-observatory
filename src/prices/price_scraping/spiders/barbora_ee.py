"""
Spider for Barbora (Estonia) — https://barbora.ee.

Unlike barbora.lt (Cloudflare-gated, per round-1 evidence), the .ee
storefront has a different WAF posture: plain curl passes everywhere
tested. No single whole-catalog endpoint was found, so this is a
two-hop harvest: (1) the site's public Constructor.io search index
(key embedded in the homepage HTML, `key_iPrSGZnKPnjLRFDN` — meant to be
public) resolves a search term to product slugs — re-verified live
2026-08-06: GET https://ac.cnstrc.com/search/piim?key=key_iPrSGZnKPnjLRFDN
-> HTTP 200, 262 results, e.g. slug 'piim-alma-2-5-proc-1-5-l' — but the
Constructor index carries no price field, only brand/description/url; (2)
each product's own page IS server-rendered with price embedded in a
`"units":[{"id":0,"price":N.NN,...}]` JSON block — re-verified live:
GET https://barbora.ee/toode/piim-alma-2-5-proc-1-5-l -> HTTP 200, 76KB,
price 1.39 (matches the site's displayed price). Category-tree API
(/api/eshop/v1/category/offertree) also works unauthenticated but no
category->products listing route was found, so a common-noun search
sweep is used to seed product slugs instead of a category walk.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://ac.cnstrc.com/search/{term}"
_CIO_KEY = "key_iPrSGZnKPnjLRFDN"
_PRODUCT_BASE = "https://barbora.ee/toode/"
_PRICE_RE = re.compile(r'"units":\[\{"id":0,"price":([\d.]+)')
_TITLE_RE = re.compile(r"<title>([^<]+)</title>")

_SEARCH_TERMS = [
    "piim",
    "leib",
    "juust",
    "munad",
    "liha",
    "kana",
    "kala",
    "jogurt",
    "või",
    "suhkur",
    "jahu",
    "riis",
    "pasta",
    "kohv",
    "tee",
    "mahl",
    "vesi",
    "õlu",
    "vein",
    "šokolaad",
    "küpsised",
    "konservid",
    "köögiviljad",
    "puuviljad",
    "vorst",
]
_RESULTS_PER_TERM = 20


class BarboraEeSpider(scrapy.Spider):
    name = "barbora_ee"
    allowed_domains = ["barbora.ee", "cnstrc.com"]
    currency = "EUR"
    language = "et"

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
                dont_filter=False,
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
