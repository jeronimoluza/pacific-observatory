"""Spider for Sushiya (sushiya.ua) — Ukraine restaurant / takeaway menu.

Sushiya is Ukraine's largest fast-casual sushi chain (21 restaurants across 5
cities). Its catalogue is a Magento storefront with fully server-rendered menu
pages (Tier 1A, no Playwright): each dish is an ``li.product-item`` whose name
sits in ``a.product-item-link`` and whose price is the ``span.price`` inside the
``finalPrice`` wrapper ("395 ₴"). We collect a spread of menu categories as the
COICOP 11.1 (restaurants / catering) layer of the PPP basket — the one division
otherwise only represented by accommodation.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://sushiya.ua/{cat}/"

# Confirmed server-rendered menu categories (slug -> stable English label).
CATEGORIES = [
    ("rolli", "Rolls"),
    ("seti", "Sets"),
    ("sushi", "Sushi"),
    ("supy", "Soups"),
    ("napitki", "Drinks"),
    ("zakuski", "Appetizers"),
]

_DIGITS_RE = re.compile(r"\d[\d\s\xa0]*")
_ID_RE = re.compile(r"/([^/]+?)\.html")


class SushiyaUaSpider(scrapy.Spider):
    name = "sushiya_ua"
    allowed_domains = ["sushiya.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        for cat, label in CATEGORIES:
            yield scrapy.Request(
                _BASE.format(cat=cat),
                callback=self.parse_menu,
                meta={"category": label},
            )

    def parse_menu(self, response):
        label = response.meta.get("category")
        items = response.css("li.product-item")
        logger.info("sushiya_ua: %s -> %d items", label, len(items))
        yielded = 0
        for it in items:
            name = (it.css("a.product-item-link::text").get() or "").strip()
            href = it.css("a.product-item-link::attr(href)").get()
            # The final price is the .price span inside the finalPrice wrapper.
            price_raw = it.css(
                '.price-wrapper[data-price-type="finalPrice"] .price::text'
            ).get() or it.css("span.price::text").get()
            if not name or not href or not price_raw:
                continue
            m = _DIGITS_RE.search(price_raw)
            if not m:
                continue
            price = re.sub(r"[\s\xa0]", "", m.group(0))
            if not price.isdigit():
                continue
            sm = _ID_RE.search(href)
            yield {
                "product_id": sm.group(1) if sm else None,
                "product_name": name[:500],
                "price": price,
                "currency": self.currency,
                "category": f"Restaurant menu — {label}",
                "url": response.urljoin(href),
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1
        logger.info("sushiya_ua: yielded %d from %s", yielded, label)
