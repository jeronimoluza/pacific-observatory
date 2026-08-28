"""
Spider for shophive.com — Pakistan electronics retailer (Magento).

Custom Magento storefront (MageBig martfury theme). No public sitemap listed
in robots.txt, so this walks the top-level category nav instead of a product
sitemap. Each category listing page (e.g. /apple/iphone) is standard Magento
markup: `<a class="product-item-link" href="...">NAME</a>` followed by a
`price-box price-final_price` block with `data-product-id` and
`data-price-amount` on the price span — same structure verified live on
2026-08-17 for /apple/iphone (real PKR prices e.g. Rs 549,999.00 for an
Apple iPhone 17 Pro Max, data-price-amount="549999").

Pagination is Magento-standard `?p=N`; walked until the `action next` link
disappears, capped at MAX_PAGES per category to bound runtime across the
~14 top-level categories.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.shophive.com"
_TOP_CATEGORIES = [
    "apple",
    "mobile-phones",
    "laptops-computers",
    "tv",
    "audio",
    "appliances",
    "cameras",
    "tablets",
    "video-games",
    "office-products",
    "smart-watches",
]
MAX_PAGES = 40

_CARD_RE = re.compile(r'class="product-item-link"')
_NAME_HREF_RE = re.compile(
    r'href="(https://www\.shophive\.com/[^"]+)"[^>]*title="([^"]*)"'
)
_PRICE_RE = re.compile(r'data-price-amount="([\d.]+)"\s+data-price-type="finalPrice"')
_ID_RE = re.compile(r'data-product-id="(\d+)"')
_NEXT_RE = re.compile(r'class="[^"]*\baction\s+next\b[^"]*"')


class ShophivePkSpider(scrapy.Spider):
    name = "shophive_pk"
    allowed_domains = ["shophive.com"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        text = response.text

        starts = [m.start() for m in _CARD_RE.finditer(text)]
        starts.append(len(text))
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i in range(len(starts) - 1):
            # the price block follows the name link but sits outside the
            # narrow starts[i]:starts[i+1] slice on this template, so widen
            # the window forward (never past the next card, to avoid
            # attributing a neighboring card's price to this one)
            window = text[starts[i] : min(starts[i] + 2500, starts[i + 1])]
            name_m = _NAME_HREF_RE.search(window)
            price_m = _PRICE_RE.search(window)
            id_m = _ID_RE.search(window)
            if not (name_m and price_m):
                continue
            n += 1
            yield {
                "product_id": id_m.group(1)
                if id_m
                else name_m.group(1).rsplit("/", 1)[-1],
                "product_name": html.unescape(name_m.group(2)).strip()[:500],
                "category": slug,
                "price": price_m.group(1),
                "currency": self.currency,
                "available": True,
                "url": name_m.group(1),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if page < MAX_PAGES and _NEXT_RE.search(text):
            yield scrapy.Request(
                f"{_BASE}/{slug}?p={page + 1}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": page + 1},
            )
