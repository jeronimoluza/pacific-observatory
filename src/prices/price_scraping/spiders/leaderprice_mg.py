"""
Spider for Leader Price Madagascar — https://www.leaderprice.mg/.

Custom PHP/ExtJS-style SSR site. The department nav (Boissons, Frais, Fruits
et legumes, etc., ids sray_1..sray_12) is driven client-side with no
discoverable GET route in this pass — /Rayon/<id>, /rayon.php?id=<id> and
similar guesses all 404 or 500. What IS confirmed live and reachable by
plain GET are three fixed collection pages that each render a full,
paginate-free product grid server-side: /Nouv (new arrivals, 17 products),
/Promo (76 products), /Bio (76 products, mostly genuine grocery items:
biscuits, jam, tea, sugar, chocolate). Total ~150 distinct SSR products
across the three pages.

Each product card: `<img ... title="FULL NAME"><div class='desc'>
<p class='text2'>TRUNCATED NAME</p><p class='text2'><span>PRICE Ar</span>
</p></div>`, wrapped in `<div id='bordu_<id>' class='bordu product'>`. We use
the img title attribute for the untruncated name. Price format is
"39 900,00 Ar" (space thousands separator, comma decimal) — normalized to
plain decimal.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.leaderprice.mg"
_PAGES = ["/Nouv", "/Promo", "/Bio"]

_CARD_RE = re.compile(
    r"id='bordu_(\d+)'.*?title=\"([^\"]+)\">\s*<div class='desc'>\s*"
    r"<p class='text2'>[^<]*</p>\s*<p class='text2'><span>([^<]+)</span>",
    re.S,
)


def _parse_price(raw: str):
    value = raw.replace("Ar", "").strip()
    value = value.replace(" ", "").replace(",", ".")
    try:
        float(value)
    except ValueError:
        return None
    return value


class LeaderpriceMgSpider(scrapy.Spider):
    name = "leaderprice_mg"
    allowed_domains = ["leaderprice.mg"]
    currency = "MGA"
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
        for path in _PAGES:
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_page,
                meta={"path": path},
            )

    def parse_page(self, response):
        path = response.meta["path"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"leaderprice_mg page={path} count={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, name, raw_price in cards:
            price = _parse_price(raw_price)
            if price is None:
                logger.debug(f"no numeric price for {name!r}: {raw_price!r}")
                continue
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": path.strip("/"),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{path}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
