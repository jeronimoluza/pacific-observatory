"""
Spider for Fybeca (Ecuador) -- https://www.fybeca.com/.

Salesforce Commerce Cloud (Demandware) storefront. Category pages embed
a clean `data-gtm` impressions JSON per product tile (id/name/price/
category) alongside the rendered grid -- a hydration-payload regex pass,
same pattern as tia_ec.py, cleaner than parsing the product-tile HTML
directly. Further pages are fetched straight from the AJAX grid endpoint
`Search-UpdateGrid?cgid=<id>&start=<N>&sz=18`, which returns the same
GTM-tagged tile markup (confirmed live). `cgid` is the last URL path
segment with `-` -> `_` (e.g. /medicinas/primeros-auxilios/ ->
cgid=primeros_auxilios).

Re-verified live 2026-08-17: GET /belleza/ -> 200, cgid=belleza,
data-count=2545, page size 18, real USD prices e.g. "price":6.24.
Currency USD matches countries.yaml (Ecuador is dollarized).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.fybeca.com"
_TOP_CATEGORIES = [
    "adulto-mayor",
    "alimentos-y-bebidas",
    "bazar-y-hogar",
    "belleza",
    "bienestar-sexual",
    "bienestar",
    "cuidado-personal",
    "dermocosmetica-1",
    "infantil-y-maternidad",
    "mascotas",
    "medicinas",
    "nutricion-y-vitaminas",
]
_PAGE_SIZE = 18
MAX_PAGES_PER_CATEGORY = 25
_ITEM_RE = re.compile(
    r'"id":"(ECFY_\d+)","name":"([^"]*)","price":([\d.]+),"category":"([^"]*)"'
)


class FybecaEcSpider(scrapy.Spider):
    name = "fybeca_ec"
    allowed_domains = ["fybeca.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            cgid = slug.replace("-", "_")
            yield scrapy.Request(
                f"{_BASE}/{slug}/",
                callback=self.parse_grid,
                meta={"cgid": cgid, "start": 0},
            )

    def parse_grid(self, response):
        cgid = response.meta["cgid"]
        start = response.meta["start"]
        text = html.unescape(response.text)
        matches = _ITEM_RE.findall(text)
        for product_id, name, price, category in matches:
            name = name.strip()
            if not name or not price:
                continue
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name)[:500],
                "category": html.unescape(category) or cgid,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/on/demandware.store/Sites-FybecaEcuador-Site/"
                f"es_EC/Product-Show?pid={product_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        page = start // _PAGE_SIZE + 1
        if matches and page < MAX_PAGES_PER_CATEGORY:
            next_start = start + _PAGE_SIZE
            yield scrapy.Request(
                f"{_BASE}/on/demandware.store/Sites-FybecaEcuador-Site/es_EC/"
                f"Search-UpdateGrid?cgid={cgid}&start={next_start}&sz={_PAGE_SIZE}",
                callback=self.parse_grid,
                meta={"cgid": cgid, "start": next_start},
            )
