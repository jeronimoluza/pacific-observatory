"""
Spider for Magik (Gabès, Tunisia) — https://magik.tn/.

Custom server-rendered grocer (not the Next.js SPA round-1 flagged — that
was the product-detail page; the category listing page at
`/produits?category_id=<id>&data_from=category&page=<n>` is plain SSR HTML
with both name and price present in the raw bytes). Each product card:
`<h4>...<a href=".../produit/<slug>">NAME</a></h4>` followed by
`<h5 class="product-price">[<del>OLD PRICE</del>]<span class="text-accent
...">PRICE TND</span></h5>` — the `<del>` is the pre-discount price when
present; the `<span>` is always the current price.

Category ids scraped from /categories (27 ids: 1-17, 20, 22, 26, 28, 32, 33,
37, 38, 39, 41). Pagination is unbounded `page=N`; the site returns HTTP 200
with zero product cards once a category runs out of pages (byte size stays
~141KB), which is used as the stop condition rather than a fixed page cap.

Re-verified live 2026-08-06: GET /produits?category_id=1&data_from=category
&page=1 -> HTTP 200, 205KB, 20 real product cards. Sample: 'Courge rouge
قرع أحمر' TND 1.800 (was TND 2.000), 'Tomates طماطم' TND 1.800. page=2 ->
20 more distinct products; page=3 -> 0 (end of category). Fresh
produce/poultry/fish/dairy/charcuterie/beverages — genuine Gabès grocer per
its own SEO alt text, not a demo template.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://magik.tn"
_CATEGORY_IDS = [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    20,
    22,
    26,
    28,
    32,
    33,
    37,
    38,
    39,
    41,
]
_MAX_PAGES = 60

_CARD_RE = re.compile(
    r'<h4[^>]*>\s*<a href="https://magik\.tn/produit/([a-z0-9-]+)">\s*'
    r"([^<]+?)\s*</a>\s*</h4>\s*<div[^>]*>\s*<h5[^>]*>(.*?)</h5>",
    re.S,
)
_PRICE_RE = re.compile(r"([0-9]+\.[0-9]+)\s*TND")


def _current_price(price_block: str) -> str | None:
    prices = _PRICE_RE.findall(price_block)
    if not prices:
        return None
    return prices[-1]


class MagikTnSpider(scrapy.Spider):
    name = "magik_tn"
    allowed_domains = ["magik.tn"]
    currency = "TND"
    language = "fr"

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
        for cat_id in _CATEGORY_IDS:
            yield scrapy.Request(
                f"{_BASE}/produits?category_id={cat_id}&data_from=category&page=1",
                callback=self.parse_category,
                meta={"category_id": cat_id, "page": 1},
            )

    def parse_category(self, response):
        cat_id = response.meta["category_id"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"magik_tn: category={cat_id} page={page} products={len(cards)}")
        if not cards:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for slug, name, price_block in cards:
            price = _current_price(price_block)
            if price is None:
                continue
            yield {
                "product_id": slug,
                "product_name": name.strip()[:500],
                "category": str(cat_id),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/produit/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if page < _MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/produits?category_id={cat_id}&data_from=category&page={page + 1}",
                callback=self.parse_category,
                meta={"category_id": cat_id, "page": page + 1},
            )
