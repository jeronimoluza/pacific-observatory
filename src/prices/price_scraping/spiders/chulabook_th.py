"""ChulaBook Thailand books and school-supply homepage feed."""

import json
from datetime import datetime, timezone

import scrapy


class ChulabookThSpider(scrapy.Spider):
    name = "chulabook_th"
    allowed_domains = ["chulabook.com", "www.chulabook.com"]
    start_urls = ["https://www.chulabook.com/main-book"]
    currency = "THB"
    language = "th"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        payload = response.css("script#__NEXT_DATA__::text").get()
        if not payload:
            return
        try:
            data = json.loads(payload)
        except ValueError:
            return

        seen = set()
        for product in self._walk_products(data):
            product_id = str(product.get("id") or product.get("barcode") or "").strip()
            name = str(product.get("name") or "").strip()
            price = product.get("price")
            main_url_name = str(product.get("main_url_name") or "").strip("/")
            if not (product_id and name and main_url_name and price is not None):
                continue
            if product.get("type") and product.get("type") != "book":
                continue
            if product_id in seen:
                continue
            seen.add(product_id)
            try:
                price_value = float(price)
            except (TypeError, ValueError):
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": product.get("cate_key") or product.get("category"),
                "price": f"{price_value:.2f}",
                "currency": self.currency,
                "available": int(product.get("stock") or 0) > 0,
                "url": f"https://www.chulabook.com/{main_url_name}/{product_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    def _walk_products(self, value):
        if isinstance(value, dict):
            if "name" in value and "price" in value and ("id" in value or "barcode" in value):
                yield value
            for child in value.values():
                yield from self._walk_products(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._walk_products(child)
