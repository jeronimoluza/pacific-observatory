"""
Spider for Mercator Online (Slovenia) — https://mercatoronline.si/.

Verified live 2026-09-06 with curl_cffi impersonate="chrome124" (all 5
mandatory profiles clear cleanly, no WAF challenge). Custom PHP storefront
("Mercator (3.0)" per the page's meta name="shopVersion").

Category/browse pages (/brskaj) are a client-side SPA (hash-fragment
routing, `#categories=<id>`, no product data or API call visible in the
raw response) — a Tier-2 dead end. But `/sitemap.xml` is open (declared in
robots.txt) and lists every PDP directly: `/izdelek/<id>/<slug>`, 2026-09-06
snapshot ~3.2MB of <loc> entries — a real, large, walkable catalog.

PDP price is NOT server-rendered in the visible `.lib-product-price` span
(that ships empty and is filled by client JS) -- confirmed via a Playwright
network trace that no dedicated price XHR fires either; the price instead
lives in a GTM `analyticsObject` (`{"event":"view_item","ecommerce":
{"items":[{"item_id":...,"item_name":...,"currency":"EUR","item_brand":...,
"item_category":...,"item_category2":...,"item_category3":...,
"price":...}]}}`) already embedded server-side in the raw HTML (confirmed
via plain curl_cffi GET, no JS needed) -- so the spider reads that instead
of the empty DOM span. Sample: 'Margarina, Zvijezda, 250 g' EUR 1.09
(id 22419); 'Pšenična bela moka T-400, Farina, 1 kg' EUR 1.89 (id 22575) --
re-fetched both live, values stable and distinct per product.

The PC30 "lowest price in the preceding 30 days" field (Omnibus Directive
compliance) ships as an empty `.lib-product-pc30_price-value` div in the
same raw HTML and is not populated in analyticsObject either -- it appears
to be client-JS-filled from a source this probe pass did not locate.
Deferred: current price only for this pass.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://mercatoronline.si"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_ANALYTICS_RE = re.compile(
    r'"event":"view_item","ecommerce":\{"items":\[(\{.*?\})\]\}', re.S
)


class MercatoronlineSiSpider(scrapy.Spider):
    name = "mercatoronline_si"
    allowed_domains = ["mercatoronline.si"]
    currency = "EUR"
    language = "sl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/izdelek/" in u]
        logger.info(f"mercatoronline_si: {len(urls)} product URLs in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        m = _ANALYTICS_RE.search(response.text)
        if not m:
            logger.warning(f"mercatoronline_si: no analyticsObject on {response.url}")
            return
        try:
            item = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning(f"mercatoronline_si: bad JSON on {response.url}")
            return

        name = (item.get("item_name") or "").strip()
        price = item.get("price")
        if not name or price in (None, ""):
            return

        category_parts = [
            item.get(k)
            for k in ("item_category", "item_category2", "item_category3")
            if item.get(k)
        ]

        yield {
            "product_id": item.get("item_id")
            or response.url.rstrip("/").rsplit("/", 2)[-2],
            "product_name": name[:500],
            "category": "/".join(category_parts) if category_parts else None,
            "price": price,
            "currency": item.get("currency") or self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
