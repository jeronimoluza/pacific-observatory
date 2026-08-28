"""
Spider for Yobou Market (Benin) — https://www.yoboumarket.com/.

Custom Next.js storefront with an open, unauthenticated JSON API:
GET /api/products?limit=all&includeInactive=true -> a flat JSON array of
product objects (_id, name, description, price, category, subcategory,
inStock, stockQuantity, sku, isActive, ...). No pagination needed — the
`limit=all` param returns the whole catalog in one response.

Re-verified live 2026-08-06: HTTP 200, 578KB, 778 products, no auth. Sample:
'Chou' (cabbage) 500 FCFA, 'Biscottes au froment' 600 XOF. Prices are plain
XOF integers (no minor-unit division). General grocery/household
marketplace — walked whole catalog per instructions (categories seen:
Alimentation, Cuisine, Fruits et Legumes, Petit Dejeuner, Hygiene et
Cosmetique, Nettoyages, Electromenagers, Pagnes/tissus, Grignoter, Epices,
Savon, plus many uncategorized rows).
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://www.yoboumarket.com/api/products?limit=all&includeInactive=true"


class YoboumarketBjSpider(scrapy.Spider):
    name = "yoboumarket_bj"
    allowed_domains = ["yoboumarket.com"]
    currency = "XOF"
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
        yield scrapy.Request(_URL, callback=self.parse_page)

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        if not isinstance(products, list):
            return
        logger.info(f"yoboumarket_bj count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("price")
            if price is None:
                continue
            category = p.get("category") or None
            subcategory = p.get("subcategory") or None
            if category and subcategory:
                category = f"{category} > {subcategory}"
            product_id = str(p.get("_id") or p.get("sku") or "")
            yield {
                "product_id": product_id,
                "product_name": html.unescape(str(p.get("name") or "")).strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("inStock", True)),
                "url": f"https://www.yoboumarket.com/#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
