"""
Spider for BlueCart (Maldives) — bluecart.mv, "Online supermarket — Maldives".

Custom platform (not Odoo/Shopify/Woo — bespoke "bc-pc" product-card
markup, AjaxCart.* cart calls). No JSON API found; category pages are
plain server-rendered HTML, no JS needed.

Small catalog: `sitemap.xml` lists exactly 21 category pages and 30
individual product pages (confirmed exhaustive — no pagination markup on
any category page, and `?pagenumber=2`-style params return an empty
result). Category slugs are used as the crawl seed since they cover the
full product list without needing to fetch each PDP separately (cards
carry name/price/category/id inline).

Card markup:
    <div class="bc-pc" data-productid="1">
      <a class="bc-pc-media-link" href="/banana-1kg" title="...">
      <span class="bc-pc-badge">Fruits &amp; Vegetables</span>
      <h3 class="bc-pc-name"><a href="/banana-1kg">Banana (1kg)</a></h3>
      <div class="bc-pc-price-row"><span class="bc-pc-price">MVR 25.00</span></div>

Page family: listing only (category pages) — PDPs are never fetched.

Verified live 2026-09-11: sitemap-derived 21 categories, 30 distinct
product ids extracted, MVR read directly off `.bc-pc-price` text.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://bluecart.mv"

_CATEGORIES = [
    "pantry-staples", "canned-food", "home-baking-instant-and-staple-food",
    "breakfast-cereals-and-spreads", "maldivian-products", "breakfast-snacks",
    "biscuites-and-cookies", "groceries", "beverages", "all-beverages",
    "fruits-vegetables", "dairy-chilled", "dairy-products", "dairy-eggs",
    "frozen-group", "frozen-fish-and-meat", "snacks-beverages",
    "home-personal-care", "household-and-others", "beauty-and-hygiene",
    "baby-products", "meat-seafood", "personal-care", "household",
    "baby-care",
]

_PRICE_RE = re.compile(r"([\d,]+\.?\d*)")


class BluecartMvSpider(scrapy.Spider):
    name = "bluecart_mv"
    allowed_domains = ["bluecart.mv"]
    currency = "MVR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids: set[str] = set()

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE_URL}/{slug}",
                callback=self.parse_category,
                errback=self.errback,
            )

    def parse_category(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("div.bc-pc")
        n = 0
        for card in cards:
            pid = card.attrib.get("data-productid")
            if not pid or pid in self._seen_ids:
                continue
            self._seen_ids.add(pid)
            name = card.css("h3.bc-pc-name a::text").get()
            href = card.css("h3.bc-pc-name a::attr(href)").get()
            price_text = card.css("span.bc-pc-price::text").get()
            category = card.css("span.bc-pc-badge::text").get()
            if not name or not price_text or not href:
                continue
            m = _PRICE_RE.search(price_text.replace(",", ""))
            if not m:
                continue
            try:
                price = float(m.group(1))
            except ValueError:
                continue
            n += 1
            yield {
                "product_id": pid,
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": (category or "").strip() or None,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"bluecart_mv: {response.url} — {n} new products")

    def errback(self, failure):
        logger.error("bluecart_mv: request failed %s — %r", failure.request.url, failure.value)
