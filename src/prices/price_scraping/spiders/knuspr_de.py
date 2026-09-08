"""
Spider for Knuspr.de (Germany) -- https://www.knuspr.de/.

Knuspr is the Rohlik Group's German online grocery delivery service
(sibling to rohlik_cz/CZ, kifli_hu/HU, gurkerl_at/AT -- same Next.js
storefront family, different per-country category-id space).

Same pattern as gurkerl_at: walk the unauthenticated `sitemap_products.xml`
(2.2MB, ~15,175 product URLs of the form
`https://www.knuspr.de/{productId}-{slug}`), extract product ids from the
`<loc>` path, then batch through the shared Rohlik-platform
`/api/v1/products/card` endpoint:

  GET /api/v1/products/card?products=<id>&products=<id>...&categoryType=normal
      -> [{"productId","name","slug","unit","textualAmount",
           "prices":{"originalPrice","salePrice","currency":"EUR"},...}]

Confirmed live 2026-09-06 (100-id batch, Referer header required):
productId 125861 "Pfand € 0,15" EUR 0.15.

No category/breadcrumb from either the sitemap or the card endpoint --
category left null, same as gurkerl_at.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.knuspr.de"
_SITEMAP_URL = f"{_BASE}/sitemap_products.xml"
_LOC_RE = re.compile(r"<loc>(https://www\.knuspr\.de/(\d+)-[^<]+)</loc>")
CARD_BATCH = 100
MAX_PRODUCTS = 20000  # safety cap; sitemap currently ~15,175


class KnusprDeSpider(scrapy.Spider):
    name = "knuspr_de"
    allowed_domains = ["knuspr.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.knuspr.de/"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        pairs = _LOC_RE.findall(response.text)
        logger.info(f"knuspr_de: sitemap yielded {len(pairs)} product urls")
        pairs = pairs[:MAX_PRODUCTS]
        for i in range(0, len(pairs), CARD_BATCH):
            chunk = pairs[i : i + CARD_BATCH]
            ids = [pid for _, pid in chunk]
            url_by_id = {pid: url for url, pid in chunk}
            qs = "&".join(f"products={pid}" for pid in ids)
            yield scrapy.Request(
                f"{_BASE}/api/v1/products/card?{qs}&categoryType=normal",
                callback=self.parse_cards,
                meta={"url_by_id": url_by_id},
            )

    def parse_cards(self, response):
        url_by_id = response.meta["url_by_id"]
        try:
            cards = response.json()
        except ValueError:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            if card.get("type") != "PRODUCT":
                continue
            pid = str(card.get("productId"))
            prices = card.get("prices") or {}
            price = prices.get("salePrice") or prices.get("originalPrice")
            name = (card.get("name") or "").strip()
            if not name or price is None or price <= 0:
                continue
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": None,
                "price": price,
                "currency": prices.get("currency", self.currency),
                "available": True,
                "url": url_by_id.get(pid, f"{_BASE}/{pid}"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
