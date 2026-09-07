"""Shared parser for CP Axtra/Makro Next.js category pages."""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class MakroNextCategorySpider(scrapy.Spider):
    """Scrape product hits embedded in public Next.js category pages."""

    base_url = ""
    currency = ""
    language = "en"
    store_name = ""
    category_slugs = (
        "fruit-vegetables",
        "meat",
        "fish-seafood",
        "dry-grocery",
        "beverages",
        "household-supplies",
        "health-beauty",
    )

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 0.75,
        "RETRY_TIMES": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in self.category_slugs:
            yield scrapy.Request(
                f"{self.base_url}/en/c/{slug}",
                callback=self.parse_category,
                meta={"category_slug": slug},
                headers={"Accept": "text/html,application/xhtml+xml"},
            )

    def parse_category(self, response):
        next_data = response.css("script#__NEXT_DATA__::text").get()
        if not next_data:
            logger.warning("No __NEXT_DATA__ payload at %s", response.url)
            return

        try:
            data = json.loads(next_data)
        except json.JSONDecodeError:
            logger.warning("Invalid __NEXT_DATA__ JSON at %s", response.url)
            return

        hits = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialSearchResult", {})
            .get("hits")
            or []
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        category_slug = response.meta.get("category_slug")

        for hit in hits:
            doc = hit.get("document") if isinstance(hit, dict) else None
            if not isinstance(doc, dict):
                continue

            product_id = (
                doc.get("productId")
                or doc.get("id")
                or doc.get("sku")
                or doc.get("makroId")
            )
            name = (
                doc.get("titleEn")
                or doc.get("title")
                or (doc.get("searchTitle") or {}).get("EN")
            )
            price = doc.get("displayPrice")
            if price is None:
                price = doc.get("originalPrice")
            if product_id is None or not name or price is None:
                continue

            name = " ".join(str(name).split())
            unit = doc.get("unitSize")
            category = doc.get("deepestCategory") or category_slug
            makro_id = doc.get("makroId")
            product_url = f"{self.base_url}/en/p/{makro_id}" if makro_id else response.url

            yield {
                "product_id": str(product_id),
                "product_name": f"{name} ({unit})" if unit else str(name),
                "price": str(price),
                "currency": doc.get("priceUnit") or self.currency,
                "category": str(category).replace("-", " ") if category else None,
                "url": product_url,
                "language": self.language,
                "brand": doc.get("brand") or doc.get("brandName"),
                "store": self.store_name or doc.get("seller") or doc.get("storeCode"),
                "scraped_at_utc": scraped_at,
            }
            logger.info("Scraped product: %s", name)
