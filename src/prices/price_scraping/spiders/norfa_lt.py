"""
Spider for Norfa (Lithuania) -- https://www.norfa.lt/.

Norfa runs no online store; its whole public catalogue is the weekly
promotions site, which is plain server-rendered HTML (jQuery, no JS
execution needed). `/akcijos/` renders every current offer card in one
response.

Probed live 2026-09-11: GET https://www.norfa.lt/akcijos/ -> HTTP 200,
1.13MB, 377 `div.c-product` cards of which 314 carry a price. Card markup:
    <div class="c-product c-product--compact">
      <div class="c-product__price-stamp"><div class="c-product__price">0.99 EUR</div></div>
      <div class="c-product__name">Fasuoti lietuviski obuoliai (dyd. 55+), 1 kg</div>
Prices are plain EUR decimals with a dot separator.

Page family parsed: listing. The cards carry no per-product permalink and
no SKU id. The collection pipeline de-duplicates on item["url"], so each
row gets a synthetic `<listing-url>#<token>` where the token is the promo
image filename (unique per product, falling back to a name slug). /akciju-puslapiai/ and its two
children serve the same DOM shape for the other promo programmes.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.norfa.lt"
_LISTINGS = [
    "/akcijos/",
    "/akciju-puslapiai/akcijos/",
    "/akciju-puslapiai/praktiski-pasiulymai/",
]
_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class NorfaLtSpider(scrapy.Spider):
    name = "norfa_lt"
    allowed_domains = ["norfa.lt"]
    currency = "EUR"
    language = "lt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 120,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen: set[str] = set()

    async def start(self):
        for path in _LISTINGS:
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_listing,
                meta={"listing": path},
            )

    def parse_listing(self, response):
        listing = response.meta["listing"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in response.css("div.c-product"):
            name = card.css("div.c-product__name::text").get()
            if not name:
                name = card.css("img::attr(alt)").get()
            name = (name or "").strip()
            raw_price = (card.css("div.c-product__price::text").get() or "").strip()
            if not name or not raw_price:
                continue
            m = _PRICE_RE.search(raw_price)
            if not m:
                continue
            price = m.group(1).replace(",", ".")
            # The cards carry no permalink and no SKU, and the collection
            # pipeline de-duplicates on item["url"] -- so every row needs a
            # distinct one. The promo image filename is unique per product;
            # fall back to a name slug when an image is missing.
            img = card.css("img::attr(src)").get() or ""
            token = img.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if not token:
                token = _SLUG_RE.sub("-", name.lower()).strip("-")
            if token in self.seen:
                continue
            self.seen.add(token)
            n += 1
            yield {
                "product_id": token,
                "product_name": name,
                "category": None,
                "price": price,
                "currency": self.currency,
                "url": f"{response.url}#{token}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"norfa_lt: {listing} items={n}")
