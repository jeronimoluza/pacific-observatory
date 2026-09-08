"""Kapruka (Sri Lanka) — https://www.kapruka.com/

Server-rendered JSP category pages at /online/grocery/price/<category> embed
one <script type="application/ld+json"> Schema.org Product block per SKU
(name, url, offers.price, offers.priceCurrency=USD). Verified live
2026-09-06: dairy_products page carries 30 Product blocks (of 80 total in
the category per the page's own "Showing 1-30 of 80" counter).

Pagination is NOT server-side: ?page=2 / ?pageNo=2 return byte-identical
HTML to page 1 (confirmed — same size, same first names). The remaining
items load via client-side AJAX/infinite-scroll this spider does not
drive, so each category yields only its first ~30 SKUs. That is still a
real, non-zero sample across 26 grocery categories — acceptable for a v1
scaffold; revisit if the AJAX endpoint is reverse-engineered later.

Kapruka prices its whole catalog in USD (site markets itself as a global
gift-delivery service for "worldwide customers" sending goods to Sri
Lanka) even though fulfilment and stock are local. Emitted as USD to match
the site's own `offers.priceCurrency`; downstream consumers should treat
this as a Sri-Lanka-fulfilled but USD-denominated retail source.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.kapruka.com"

_CATEGORIES = [
    "bagged_food",
    "bakery-and-spreads-and-cereals",
    "beverages",
    "canned_food",
    "cleansers",
    "condiments",
    "confectionery_and_biscuits",
    "cut_vegetables",
    "dairy_products",
    "dessert",
    "eggs_and_oil",
    "exotic_vegetables",
    "flour_-and-_instant_mixes",
    "frozen_food",
    "global_food",
    "herbs",
    "juice_-and-_drinks",
    "pasta_and_noodles",
    "pest_control",
    "rice",
    "seafood",
    "snacks_and_sweets",
    "specialty_foods",
    "spices_and_seasoning",
    "tobacco",
    "vegetables",
    "wellness",
]

_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?"@type":\s*"Product".*?\})\s*</script>',
    re.DOTALL,
)


class KaprukaComSpider(scrapy.Spider):
    name = "kapruka_com"
    allowed_domains = ["kapruka.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/online/grocery/price/{slug}",
                callback=self.parse_category,
                cb_kwargs={"slug": slug},
            )

    def parse_category(self, response, slug):
        blocks = _LDJSON_RE.findall(response.text)
        if not blocks:
            logger.info("kapruka_com: %s has no Product ld+json blocks", slug)
            return
        seen_ids = set()
        for raw in blocks:
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            name = data.get("name")
            url = data.get("url")
            offers = data.get("offers") or {}
            price = offers.get("price")
            if not (name and url and price not in (None, "", 0)):
                continue
            product_id = url.rstrip("/").rsplit("/", 1)[-1]
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": str(name).strip()[:500],
                "category": slug,
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
