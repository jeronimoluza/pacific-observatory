"""
Spider for DiborMarket / La Ferme de Dibor (Senegal) - https://lafermededibor.com/

Custom bespoke PHP site (robots.txt discloses /api.php and /database.sqlite).
The whole catalog is served by one unauthenticated GET:
GET /api.php?type=products -> {"products": [{...}, ...]}
(the same JSON is also returned with no query string at all -- ?type= is
accepted but not required; both were verified live).

Each product: {"id": "P<digits>", "name": "...", "price": <int XOF, no
minor units>, "cat": "<slug>", "collection": "...", "img": "...",
"stock": <int>, "expiry_date": "", "unit": "..."}. 159 products confirmed
live across 9 categories (oignons-et-pomme-de-terre, legumes, fruits,
epicerie, viandes, volaille, poissons, produits_locaux,
packs_et_promotion) -- real, varied, local Senegalese produce (graded
onion/potato sacks, chicken, rice, mango), not a template-demo catalog.
"""

import html
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class DiborMarketSnSpider(scrapy.Spider):
    name = "dibor_market_sn"
    allowed_domains = ["lafermededibor.com"]
    currency = "XOF"
    language = "fr"

    API_URL = "https://lafermededibor.com/api.php?type=products"
    PRODUCT_URL = "https://lafermededibor.com/#product-{id}"

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
        yield scrapy.Request(
            self.API_URL,
            callback=self.parse_products,
            headers={"Accept": "application/json"},
        )

    def parse_products(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("dibor_market_sn: non-JSON response")
            return

        products = payload.get("products", [])
        logger.info(f"dibor_market_sn count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()

        for prod in products:
            product_id = str(prod.get("id", "")).strip()
            name = html.unescape(str(prod.get("name", ""))).strip()
            price = prod.get("price")
            if not product_id or not name or price is None:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": prod.get("cat", ""),
                "price": str(price),
                "currency": self.currency,
                "available": bool(prod.get("stock", 0)),
                "url": self.PRODUCT_URL.format(id=product_id),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
