"""
Spider for SUKASA Costa Rica (https://www.sukasa.co.cr/) - home goods /
housewares retailer (kitchen, bedroom, bathroom, furniture, appliances).
Built on the "nidux" Costa Rican e-commerce platform (media.nidux.net CDN).

Server-rendered throughout -- no Playwright needed. Category pages
(/categories/<id>/<slug>) list product cards with plain /products/<id>/<slug>
links; PDPs carry a clean schema.org `Product` JSON-LD block (name, sku,
offers.price, offers.priceCurrency=CRC).

GOTCHA: `?page=N` on a category URL does not paginate -- page 2 returns the
identical 36 products as page 1 (confirmed byte-identical link set). This
spider only walks the first (only reachable) page per category; deeper
catalog coverage would need reverse-engineering whatever AJAX/infinite-
scroll mechanism serves the rest, which was not pursued here.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.sukasa.co.cr"
_PROD_LINK_RE = re.compile(r'href="https://www\.sukasa\.co\.cr(/products/\d+/[a-z0-9-]+)"')
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?"@type"\s*:\s*"Product".*?\})\s*</script>',
    re.S,
)

_CATEGORIES = [
    "1/dormitorio",
    "2/bano",
    "3/mesa",
    "4/cocina",
    "5/entretenimiento",
    "6/bienestar-y-salud",
    "7/terraza-y-jardin",
    "8/organizacion",
    "9/decoracion",
    "10/equipaje",
    "11/linea-blanca",
    "75/muebles",
    "76/parrillas-y-bbq",
]


class SukasaCrSpider(scrapy.Spider):
    name = "sukasa_cr"
    allowed_domains = ["sukasa.co.cr", "www.sukasa.co.cr"]
    currency = "CRC"
    language = "es"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def start_requests(self):
        for cat in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/categories/{cat}",
                callback=self.parse_category,
                meta={"category": cat},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        links = sorted(set(_PROD_LINK_RE.findall(response.text)))
        logger.info(f"sukasa_cr: category={category} products={len(links)}")
        for path in links:
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_product,
                meta={"category": category},
            )

    def parse_product(self, response):
        m = _LDJSON_RE.search(response.text)
        if not m:
            logger.warning(f"sukasa_cr: no Product JSON-LD at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning(f"sukasa_cr: malformed JSON-LD at {response.url}")
            return

        name = data.get("name")
        offer = data.get("offers") or {}
        price = offer.get("price")
        if not name or price is None:
            return

        yield {
            "product_id": data.get("sku") or data.get("productID"),
            "product_name": name,
            "price": price,
            "currency": offer.get("priceCurrency") or self.currency,
            "category": response.meta.get("category", "").split("/")[-1],
            "url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
