"""Beauty and personal-care catalogue from Boutiqaat Kuwait."""

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"(\d+(?:\.\d{3})?)\s*KWD\b", re.I)


class BoutiqaatKwSpider(scrapy.Spider):
    name = "boutiqaat_kw"
    allowed_domains = ["boutiqaat.com", "www.boutiqaat.com"]
    start_urls = ["https://www.boutiqaat.com/en-kw/women/beauty/t/"]

    def parse(self, response):
        for card in response.css("article, li.product, [class*='product-card'], [class*='productCard']"):
            name = (card.css("h2::text, h3::text, [class*='name']::text, [class*='title']::text").get() or "").strip()
            href = card.css("a::attr(href)").get()
            prices = PRICE_RE.findall(" ".join(card.css("::text").getall()))
            if not name or not prices:
                continue
            # Sale layouts present list price first and current price second.
            current = prices[-1]
            yield {
                "product_name": name,
                "price": current,
                "regular_price": prices[0] if len(prices) > 1 else None,
                "currency": "KWD",
                "available": "sold out" not in " ".join(card.css("::text").getall()).lower(),
                "url": response.urljoin(href) if href else response.url,
                "language": "en",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        next_url = response.css("a[rel='next']::attr(href), a.next::attr(href)").get()
        if next_url:
            yield response.follow(next_url, self.parse)
