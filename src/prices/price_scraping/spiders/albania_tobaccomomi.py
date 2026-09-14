"""Scrape current cigar cards from Tobacco Momi Albania."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


class AlbaniaTobaccoMomiSpider(scrapy.Spider):
    name = "albania_tobaccomomi"
    allowed_domains = ["tobaccomomi.com", "www.tobaccomomi.com"]
    start_urls = ["https://tobaccomomi.com/cigars/?currency=ALL"]

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css(".ut2-gl__item"):
            product_id = (card.css("input[name*=product_id]::attr(value)").get() or "").strip()
            link = card.css("a.product-title")
            href = (link.attrib.get("href") or "").strip() if link else ""
            name = (link.attrib.get("title") or "").strip() if link else ""
            price_parts = [part.strip() for part in card.css(".ty-price .ty-price-num::text").getall()]
            if not (product_id.isdigit() and href and name and any("Lek" in p for p in price_parts)):
                continue
            digits = re.sub(r"\D", "", price_parts[0]) if price_parts else ""
            if not digits or int(digits) <= 0:
                continue
            stock_text = " ".join(card.css("[id^=in_stock_info_] ::text").getall()).lower()
            yield {
                "product_id": product_id,
                "product_name": " ".join(name.split())[:500],
                "price": str(int(digits)),
                "currency": "ALL",
                "country": "Albania",
                "sector": "consumer_goods",
                "available": "nuk" not in stock_text,
                "url": response.urljoin(href),
                "language": "sq",
                "scraped_at_utc": scraped_at,
            }
