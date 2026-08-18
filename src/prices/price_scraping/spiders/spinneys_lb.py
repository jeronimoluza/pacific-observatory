"""
Spider for spinneyslebanon.com — Lebanon supermarket chain (Magento).

Verified live 2026-08-17: Magento storefront (`price-box price-final_price`
markup, `data-product-id` + `data-price-amount` on the price span, same
pattern as jarir/btech's Magento siblings). GraphQL is admin-auth-gated
(403) and a guessed VTEX endpoint 404's, so this scrapes SSR category
listing pages instead. Real USD prices confirmed e.g. "CANDIA UHT MILK
ENTIER" -> data-price-amount="1.85", $ 1.85; also a live "USD = 89,700"
LBP FX-rate widget on the homepage (site prices in USD, not LBP).

Walks all top-level category slugs harvested from the homepage nav —
alcohol, baby-child, bakery, beauty-personal-care, beverages, cellar,
cleaning-household, deli-dairy-eggs, electronics-appliances,
food-cupboards, frozen, fruits-vegetables, healthy-living, home-outdoor,
ice-cream, imported-for-you, meat-seafood, min-el-dayaa, party-shop,
petfection, promotions, snacks-candy, summer-essentials, tobacco,
tobacco, waitrose, world-foods — i.e. the full grocery catalog (this is
the highest food-coverage source in the batch), not just electronics.
Pagination is Magento-standard `/<slug>.html?p=N`, followed via the
`action next` link, capped at MAX_PAGES per category to bound runtime.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.spinneyslebanon.com/default"
_TOP_CATEGORIES = [
    "alcohol",
    "baby-child",
    "bakery",
    "beauty-personal-care",
    "beverages",
    "cellar",
    "cleaning-household",
    "deli-dairy-eggs",
    "electronics-appliances",
    "food-cupboards",
    "frozen",
    "fruits-vegetables",
    "healthy-living",
    "home-outdoor",
    "ice-cream",
    "imported-for-you",
    "meat-seafood",
    "min-el-dayaa",
    "party-shop",
    "petfection",
    "snacks-candy",
    "summer-essentials",
    "tobacco",
    "waitrose",
    "world-foods",
]
MAX_PAGES = 60

_CARD_RE = re.compile(r'class="product-item-link"')
_NAME_HREF_RE = re.compile(r'href="([^"]+)"[^>]*>\s*([^<]*?)\s*</a>')
_PRICE_RE = re.compile(
    r'data-product-id="(\d+)"[^>]*>.*?data-price-amount="([\d.]+)"', re.DOTALL
)
_NEXT_RE = re.compile(r'class="[^"]*\baction\s+next\b[^"]*"')


class SpinneysLbSpider(scrapy.Spider):
    name = "spinneys_lb"
    allowed_domains = ["spinneyslebanon.com"]
    currency = "USD"
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
                f"{_BASE}/{slug}.html",
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
            window = text[starts[i] : min(starts[i] + 3000, starts[i + 1])]
            name_m = _NAME_HREF_RE.search(window)
            price_m = _PRICE_RE.search(window)
            if not (name_m and price_m and name_m.group(2).strip()):
                continue
            n += 1
            yield {
                "product_id": price_m.group(1),
                "product_name": name_m.group(2).strip()[:500],
                "category": slug,
                "price": price_m.group(2),
                "currency": self.currency,
                "available": True,
                "url": name_m.group(1),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if page < MAX_PAGES and _NEXT_RE.search(text):
            yield scrapy.Request(
                f"{_BASE}/{slug}.html?p={page + 1}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": page + 1},
            )
