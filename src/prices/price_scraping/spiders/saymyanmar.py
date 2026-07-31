"""
Spider for Say Myanmar (Myanmar) - https://saymyanmar.com/

Nationwide online pharmacy on a custom Laravel/Mongo stack with an
OpenCart-style server-rendered catalogue. The homepage links to category
pages (/category/{objectid}); each category page renders product cards
(div.product-layout) carrying the product name, a /product/{objectid} link
and a numeric MMK price. Categories paginate via ?page=N. Some out-of-stock
SKUs display a price of 0 (kept, flagged unavailable).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://saymyanmar.com"
MAX_PAGES = 50
ID_RE = re.compile(r"/product/([a-f0-9]{24})")


class SaymyanmarSpider(scrapy.Spider):
    name = "saymyanmar"
    allowed_domains = ["saymyanmar.com"]
    currency = "MMK"
    language = "my"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        yield scrapy.Request(BASE_URL, callback=self.parse_home)

    def parse_home(self, response):
        cats = set(re.findall(r"/category/([a-f0-9]{24})", response.text))
        for cid in cats:
            url = f"{BASE_URL}/category/{cid}"
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"cat": cid, "page": 1}
            )

    def parse_category(self, response):
        cat = response.meta["cat"]
        page = response.meta["page"]
        count = 0
        for card in response.css("div.product-layout"):
            name = card.css("h5.product-name a::attr(title)").get()
            if not name:
                name = card.css("h5.product-name a::text").get()
            href = card.css("h5.product-name a::attr(href)").get() or ""
            price = card.css("span.price span[id^='price-']::text").get()
            if price is None:
                price = card.css("span.price ::text").re_first(r"[\d,]+")
            if not name or price is None:
                continue
            price = price.replace(",", "").strip()
            m = ID_RE.search(href)
            count += 1
            yield {
                "product_id": m.group(1) if m else None,
                "product_name": name.strip()[:500],
                "brand": None,
                "category": cat,
                "price": price,
                "currency": self.currency,
                "available": price not in ("0", ""),
                "url": href or None,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"saymyanmar cat={cat} page={page} count={count}")
        nxt = page + 1
        if count > 0 and page < MAX_PAGES and f"page={nxt}" in response.text:
            yield scrapy.Request(
                f"{BASE_URL}/category/{cat}?page={nxt}",
                callback=self.parse_category,
                meta={"cat": cat, "page": nxt},
            )
