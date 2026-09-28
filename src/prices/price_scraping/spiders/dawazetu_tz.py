"""
Spider for DawaZetu (Tanzania) — https://dawazetu.com/.

Server-rendered pharmacy storefront (custom theme, Bootstrap-based). Full
catalog paginated at `/Product?page=N`, ~21 items/page, each card carrying
product name (img alt on `a.product-link`), category, unit and price
directly in the HTML:

    <div class="product-card-modern">
      <button class="action-btn wishlist-btn" ... data-product-id="2">
      <a href="/product/ibuprofen-400mg" class="product-link">
        <img ... alt="Ibuprofen 400mg" class="product-image" />
      </a>
      <div class="product-content">
        <div class="product-category">Health Conditions - Pain &amp; Fever</div>
        <h6 class="product-name"><a href="/product/ibuprofen-400mg">Ibuprofen 400mg</a></h6>
        <div class="product-price-section"><span class="current-price">TSh 6,000</span></div>

Paginate until a page returns zero product cards.

Re-verified live 2026-09-28: GET /Product?page=1 -> 200, 21 real product
cards incl. "Ibuprofen 400mg" TSh 6,000, "Panadol Extra" TSh 20,000.
Page 2 returns a fully distinct set (household/personal-care items).
Currency TZS matches countries.yaml (site displays "TSh").
Pagination confirmed up to page=11 in the rendered page-1 nav.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://dawazetu.com"
MAX_PAGES = 100  # safety cap


class DawazetuTzSpider(scrapy.Spider):
    name = "dawazetu_tz"
    allowed_domains = ["dawazetu.com"]
    currency = "TZS"
    language = "en"

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
        yield scrapy.Request(
            f"{_BASE}/Product?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = response.css("div.product-card-modern")
        logger.info(f"dawazetu_tz page={page} count={len(cards)}")
        if not cards:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            product_id = card.css(".wishlist-btn::attr(data-product-id)").get()
            name = card.css("a.product-link img::attr(alt)").get()
            href = card.css("a.product-link::attr(href)").get()
            category = card.css(".product-category::text").get()
            price_text = card.css(".current-price::text").get()
            if not name or not href or not price_text:
                continue
            m = re.search(r"[\d,]+", price_text)
            if not m:
                continue
            price = m.group(0).replace(",", "")
            if price in ("0", ""):
                continue
            yield {
                "product_id": product_id or href.rsplit("/", 1)[-1],
                "product_name": name.strip()[:500],
                "category": category.strip() if category else None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{href}" if href.startswith("/") else href,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/Product?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
