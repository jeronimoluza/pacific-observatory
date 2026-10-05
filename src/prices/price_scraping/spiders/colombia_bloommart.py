"""Bloommart Colombia Shopify collection spider."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


class ColombiaBloommartSpider(scrapy.Spider):
    name = "colombia_bloommart"
    allowed_domains = ["www.bloommart.co"]
    start_urls = ["https://www.bloommart.co/collections/tabaco"]
    currency = "COP"

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css(".grid-product[data-product-id]"):
            product_id = (card.attrib.get("data-product-id") or "").strip()
            link = card.css("a.grid-product__link")
            href = (link.attrib.get("href") or "").strip() if link else ""
            name = " ".join(card.css(".grid-product__title::text").getall()).strip()
            price_text = " ".join(card.css(".grid-product__price::text, .grid-product__price *::text").getall())
            price_text = " ".join(price_text.split())
            if not (product_id.isdigit() and href.startswith("/collections/") and name):
                continue
            if "COP" not in price_text:
                continue
            match = re.search(r"(?:\$\s*)?([0-9][0-9.]*)\s*COP\b", price_text)
            if not match:
                continue
            try:
                amount = Decimal(match.group(1).replace(".", ""))
            except InvalidOperation:
                continue
            if amount <= 0:
                continue
            row = {
                "product_id": product_id,
                "product_name": name[:500],
                "price": str(amount),
                "currency": self.currency,
                "country": "Colombia",
                "sector": "consumer_goods",
                "url": response.urljoin(href),
                "available": True,
                "scraped_at_utc": scraped_at,
            }
            if price_text.startswith("De"):
                row["price_caveat"] = "Observed minimum/current variant price; the storefront prefix 'De' indicates the product may have higher-priced variants."
            yield row
