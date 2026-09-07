"""FoodMap Vietnam category HTML scraper."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy


class FoodmapVnSpider(scrapy.Spider):
    name = "foodmap_vn"
    allowed_domains = ["foodmap.asia"]
    currency = "VND"
    language = "vi"

    start_urls = [
        "https://foodmap.asia/category/tra-ca-phe-socola",
        "https://foodmap.asia/category/do-uong",
        "https://foodmap.asia/category/do-say-banh-keo-an-vat",
        "https://foodmap.asia/category/trai-cay-tuoi-ngon",
    ]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "COOKIES_ENABLED": False,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                f"{url}?sort=latest&page=1",
                callback=self.parse_listing,
                headers={"X-Requested-With": "XMLHttpRequest"},
                meta={"page": 1, "category_url": url},
            )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css(".item.product_box")
        for card in cards:
            item = self._item(card, response, scraped_at)
            if item:
                yield item

        page = response.meta["page"]
        if cards and page < 10:
            category_url = response.meta["category_url"]
            yield scrapy.Request(
                f"{category_url}?sort=latest&page={page + 1}",
                callback=self.parse_listing,
                headers={"X-Requested-With": "XMLHttpRequest"},
                meta={"page": page + 1, "category_url": category_url},
            )

    def _item(self, card, response, scraped_at: str):
        name = card.css("h3 a::text").get()
        url = card.css("h3 a::attr(href), a.img-full::attr(href)").get()
        product_id = card.attrib.get("data-product-id")
        sku = card.css(".detail_add_to_cart_3::attr(data-sku)").get()
        price_text = card.css(".price strong::text").get()
        price = self._price(price_text)
        if not (name and price):
            return None
        return {
            "product_id": (sku or product_id or "").strip(),
            "product_name": html.unescape(name).strip()[:500],
            "category": self._category(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.urljoin(url) if url else response.url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _price(raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = re.sub(r"[^0-9]", "", raw)
        if not cleaned:
            return None
        return str(int(cleaned))

    @staticmethod
    def _category(response) -> str | None:
        title = response.css(".brand-title h1::text").get()
        if title:
            return title.strip()
        slug = response.meta.get("category_url", "").rstrip("/").split("/")[-1]
        return slug.replace("-", " ") if slug else None
