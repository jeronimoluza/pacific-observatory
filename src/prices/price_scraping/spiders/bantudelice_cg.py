"""
Spider for BantuDelice -- https://bantudelice.cg/ (Congo Republic /
Brazzaville restaurant food-delivery marketplace).

Confirmed live 2026-09-06. Plain curl 200s fine, no anti-bot. `/robots.txt`
and `/sitemap.xml` both 404 to a custom error page, so this spider seeds
from `/restaurants` (a plain directory of `/restaurant/view/<id>` links,
8 restaurants at fetch time, no pagination) rather than a sitemap.

Each `/restaurant/view/<id>` page server-renders its full menu inline --
no separate PDP fetch needed: `<h3 class="product-name">NAME</h3>` /
`<span class="product-price">1 000 FCFA</span>` pairs per product card,
with a canonical `/plat/<id>/<slug>` link used as the item URL. Currency
FCFA = XAF, Congo Republic's currency per countries.yaml.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://bantudelice.cg"
_LISTING_URL = f"{_BASE}/restaurants"

_RESTAURANT_LINK_RE = re.compile(r"/restaurant/view/(\d+)")
_PRODUCT_CARD_RE = re.compile(
    r'<h3 class="product-name">(?P<name>.*?)</h3>.*?'
    r'<span class="product-price">(?P<price>[\d\s.,]+)\s*FCFA</span>'
    r'.*?href="(?P<url>https://bantudelice\.cg/plat/\d+/[^"]*)"',
    re.S,
)


def _parse_fcfa(raw: str) -> float | None:
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    return float(digits)


class BantudeliceCgSpider(scrapy.Spider):
    name = "bantudelice_cg"
    allowed_domains = ["bantudelice.cg"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_LISTING_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        ids = sorted({int(m) for m in _RESTAURANT_LINK_RE.findall(response.text)})
        logger.info("bantudelice_cg: %d restaurants found", len(ids))
        for rid in ids:
            yield scrapy.Request(
                f"{_BASE}/restaurant/view/{rid}",
                callback=self.parse_restaurant,
                meta={"restaurant_id": rid},
            )

    def parse_restaurant(self, response):
        restaurant_id = response.meta["restaurant_id"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for m in _PRODUCT_CARD_RE.finditer(response.text):
            name = re.sub(r"<[^>]+>", "", m.group("name")).strip()
            price = _parse_fcfa(m.group("price"))
            if not name or price is None or price <= 0:
                continue
            yield {
                "product_id": m.group("url").rsplit("/plat/", 1)[-1].split("/")[0],
                "product_name": name[:500],
                "category": f"restaurant_{restaurant_id}",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": m.group("url"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            n += 1
        logger.info("bantudelice_cg: restaurant %s yielded %d items", restaurant_id, n)
