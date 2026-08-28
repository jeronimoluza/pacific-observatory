"""
Spider for torob.com — Iran price-comparison aggregator (NOT a retailer).

Torob is a cross-merchant shopping-comparison engine: each result is the
*cheapest* price torob has found for a product across participating
stores ("price_prefix": "cheapest", a "shop_text" naming the winning
store), not one outlet's own shelf price. Treated here as
analytical_role: aggregate_proxy / channel: other rather than a retailer
feed — see manifest notes for the full caveat.

Verified live 2026-08-17: /search/?query=<term>&page=N embeds a
`__NEXT_DATA__` JSON blob at props.pageProps with `products` (~24-26/page),
`productsCount`, `page`, `hasMore`. Prices are quoted in Toman on-site
(price_text ends "تومان"); the numeric `price` field is already the Toman
value (confirmed price:3477000 == price_text "۳٫۴۷۷٫۰۰۰ تومان"), so — same
convention as sheypoor_ir — it is multiplied by 10 here and reported as
IRR (ISO 4217 has no Toman code).

A bare curl -A UA request gets a silently truncated response body (HTTP
200, content-length matches, JSON cut off mid-string with no closing
tags); adding ordinary Accept/Accept-Language/Referer headers resolves it
— no TLS/UA impersonation involved. Guessed /category/<id>/<slug>/
browsing URLs 404'd, so this walks a fixed list of representative search
queries spanning food/grocery + a few durables, each paginated via
hasMore, capped at MAX_PAGES/query.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_QUERIES = [
    "برنج",  # rice
    "روغن",  # cooking oil
    "شیر",  # milk
    "مرغ",  # chicken
    "گوشت",  # meat
    "شکر",  # sugar
    "چای",  # tea
    "پنیر",  # cheese
    "موبایل",  # mobile phone
    "یخچال",  # fridge
    "لپ تاپ",  # laptop
    "لباسشویی",  # washing machine
    "تلویزیون",  # TV
]
MAX_PAGES = 10
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class TorobIrSpider(scrapy.Spider):
    name = "torob_ir"
    allowed_domains = ["torob.com"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            "Referer": "https://torob.com/",
        },
    }

    async def start(self):
        for query in _QUERIES:
            yield scrapy.Request(
                f"https://torob.com/search/?query={quote(query)}&page=1",
                callback=self.parse_search,
                meta={"query": query, "page": 1},
            )

    def parse_search(self, response):
        query = response.meta["query"]
        page = response.meta["page"]
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(
                "torob_ir: no __NEXT_DATA__ for query=%s page=%s", query, page
            )
            return
        try:
            data = json.loads(m.group(1))
        except (ValueError, TypeError):
            logger.warning("torob_ir: bad JSON for query=%s page=%s", query, page)
            return

        pp = data.get("props", {}).get("pageProps", {})
        products = pp.get("products") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for p in products:
            name = p.get("name1")
            price = p.get("price")
            key = p.get("random_key")
            if not name or price in (None, "", 0):
                continue
            n += 1
            yield {
                "product_id": key,
                "product_name": str(name).strip()[:500],
                "category": query,
                "price": str(int(price) * 10),
                "currency": self.currency,
                "available": True,
                "url": f"https://torob.com{p.get('web_client_absolute_url', '')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: query={query} page={page} products={n}")

        if page < MAX_PAGES and pp.get("hasMore"):
            yield scrapy.Request(
                f"https://torob.com/search/?query={quote(query)}&page={page + 1}",
                callback=self.parse_search,
                meta={"query": query, "page": page + 1},
            )
