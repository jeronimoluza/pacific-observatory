"""
Spider for Europroduct (Georgia) — https://europroduct.ge/.

Custom PHP-ish storefront, server-rendered category listing pages at
/products?pcat_idIn=<id> (page 1) and /products/page-<n>?pcat_idIn=<id>
(page n>1). 16 top-level category ids cover the full catalog (subcategory
ids under each top-level id are a refinement of the same listing, not a
disjoint partition, so walking the 16 top-level ids alone is sufficient).

Re-verified live 2026-08-06: GET /products?pcat_idIn=126 -> 200, 91KB, 21
product cards incl. 'კურკუმა (50გ)' (turmeric) 3,15 ₾. Prices consistently
use the Lari sign (₾) -- matches countries.yaml GEL, no currency mismatch.
Product names are Georgian even on the /en/ UI variant, so language=ka.

Each product card:
<div class="product-grid-item js-product-item">...data-id="<SKU>"...
<h2 class="product-name"><a href="...">NAME</a></h2>...
<span class="product-price"><span>PRICE ₾</span></span>
Sale items instead render <span class="new">PRICE</span><span class="old">..
</span> -- the "new" (current) price is used.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://europroduct.ge"
_TOP_CATEGORY_IDS = [
    126,
    130,
    132,
    135,
    139,
    140,
    143,
    145,
    146,
    147,
    148,
    150,
    151,
    152,
    291,
    302,
]
MAX_PAGES = 60  # safety cap per category (cat 126 alone runs to page-33)

_CARD_RE = re.compile(
    r'class="product-grid-item js-product-item".*?data-id="([0-9A-Fa-f]+)".*?'
    r'<h2 class="product-name">\s*<a[^>]*>([^<]+)</a>.*?'
    r'<span class="product-price">\s*(?:<span class="new">([^<]+)</span>'
    r"|<span>([^<]+)</span>)",
    re.S,
)


class EuroproductGeSpider(scrapy.Spider):
    name = "europroduct_ge"
    allowed_domains = ["europroduct.ge"]
    currency = "GEL"
    language = "ka"

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
        for cat_id in _TOP_CATEGORY_IDS:
            yield scrapy.Request(
                f"{_BASE}/products?pcat_idIn={cat_id}",
                callback=self.parse_page,
                meta={"cat_id": cat_id, "page": 1},
            )

    def parse_page(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"europroduct_ge: cat={cat_id} page={page} cards={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, name, new_price, plain_price in cards:
            price = new_price or plain_price
            price = price.replace("₾", "").strip().replace(",", ".")
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": str(cat_id),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/products/product/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/products/page-{nxt}?pcat_idIn={cat_id}",
                callback=self.parse_page,
                meta={"cat_id": cat_id, "page": nxt},
            )
