"""Virtual Bazaar Jordan Shopify homepage consumer-goods prices."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)\s+USD", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


class VirtualBazaarJoSpider(scrapy.Spider):
    name = "virtual_bazaar_jo"
    allowed_domains = ["virtual-bazaar.com"]
    start_urls = ["https://virtual-bazaar.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    def parse(self, response):
        seen = set()
        for card in response.css(".product-card-wrapper"):
            link = card.css('a[href^="/products/"]::attr(href)').get()
            name = clean(card.css("h3 a::text").get())
            raw = clean(card.css(".price-item--regular::text").get())
            match = PRICE_RE.search(raw)
            if not (link and name and match):
                continue
            url = response.urljoin(link).split("#", 1)[0]
            if url in seen or "gift-card" in url:
                continue
            seen.add(url)
            yield {
                "product_id": url.rstrip("/").rsplit("/", 1)[-1][:250],
                "product_name": name[:500],
                "price": match.group(1).replace(",", ""),
                "currency": "USD",
                "country": "Jordan",
                "sector": "consumer_goods",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
