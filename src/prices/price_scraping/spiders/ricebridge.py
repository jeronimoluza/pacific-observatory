"""Rice and essentials delivered to families in Greater Monrovia, Liberia."""

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


class RicebridgeSpider(scrapy.Spider):
    name = "ricebridge"
    allowed_domains = ["ourricebridge.com", "www.ourricebridge.com"]
    start_urls = ["https://www.ourricebridge.com/"]

    def parse(self, response):
        for heading in response.css("a[href^='/shop/'] h3"):
            card = heading.xpath("ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' group ')][1]")
            text = " ".join(t.strip() for t in card.css("::text").getall() if t.strip())
            match = PRICE_RE.search(text)
            name = " ".join(heading.css("::text").getall()).strip()
            if not name or not match:
                continue
            href = card.css("a[href^='/shop/']::attr(href)").get()
            yield {
                "product_name": name,
                "package_size": " ".join(card.css("p::text").getall()).strip(),
                "price": match.group(1).replace(",", ""),
                "currency": "USD",
                "available": True,
                "locality": "Greater Monrovia, Liberia",
                "channel": "diaspora_delivery",
                "delivery_included": True,
                "url": response.urljoin(href) if href else response.url,
                "language": "en",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
