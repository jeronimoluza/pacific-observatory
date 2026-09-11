"""Spider for Juba Fashion Hub (South Sudan) -- https://jubafashionhub.link/.

Bespoke React SPA (Vite/Firebase-style build, client-side routing -- any path
under the origin serves the same index.html). Not Shopify/Woo/Presta/OpenCart.
The catalog is served whole, in one shot, by a same-origin JSON endpoint at
GET /api/products -- no auth, no pagination, no query params. 130 items,
perfumes/skincare, each carrying both priceUSD and priceSSP; South Sudan's
own currency is SSP so priceSSP is used. Single fixed-size catalog (no
pagination to enumerate across), confirmed by re-fetching /api/products and
comparing item id sets -- identical both times, consistent with "no
pagination" rather than a broken paginator.

Per-item permalinks don't exist in the payload (no slug/href field); the SPA
resolves any /product/<id> path client-side (confirmed: returns the same
index.html shell, HTTP 200), so that path is used as a stable, unique
canonical url per item for dedup purposes even though it is never itself
fetched.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://jubafashionhub.link"
API_URL = f"{BASE}/api/products"


class JubaFashionHubLinkSsSpider(scrapy.Spider):
    name = "juba_fashion_hub_link_ss"
    allowed_domains = ["jubafashionhub.link"]
    currency = "SSP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
    }

    async def start(self):
        yield scrapy.Request(API_URL, callback=self.parse_products)

    def parse_products(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"juba_fashion_hub_link_ss: non-JSON response at {response.url}")
            return
        if not isinstance(products, list):
            return
        logger.info(f"juba_fashion_hub_link_ss: count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item

    def _item(self, p: dict):
        price = p.get("priceSSP")
        if price is None:
            return None
        pid = str(p.get("id") or "").strip()
        if not pid:
            return None
        cat = p.get("collectionSlug")
        return {
            "product_id": pid,
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": cat,
            "price": str(price),
            "currency": self.currency,
            "available": bool((p.get("stockCount") or 0) > 0),
            "url": f"{BASE}/product/{pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
