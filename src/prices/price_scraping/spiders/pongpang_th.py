"""Pongpang Thailand discount household and general-goods storefront."""

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")


class PongpangThSpider(scrapy.Spider):
    name = "pongpang_th"
    allowed_domains = ["pongpang.net", "www.pongpang.net"]
    start_urls = ["https://pongpang.net/product.php?cat=all"]
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
        for card in response.css("div.pong-card"):
            name = " ".join(card.css("div.pong-name::text").getall()).strip()
            if not name:
                name = " ".join(card.css("img::attr(alt)").getall()).strip()
            price_text = " ".join(card.css("div.pong-price::text").getall()).strip()
            m = _PRICE_RE.search(price_text)
            if not name or not m:
                continue
            try:
                price = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            product_id = (card.css("div.pong-item-id::text").get() or "").strip()
            product_ref = product_id or card.attrib.get("id", "")
            product_fragment = re.sub(r"[^A-Za-z0-9_-]+", "-", product_ref).strip("-")
            unit = " ".join(card.css("div.pong-price small::text").getall()).strip()
            yield {
                "product_id": product_ref,
                "product_name": name[:500],
                "category": "discount household, toys, kitchen, tools, general goods",
                "price": f"{price:.2f}",
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#product-{product_fragment}" if product_fragment else response.url,
                "language": self.language,
                "notes": unit,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
