import re
from datetime import datetime, timezone

import scrapy


class EcuadorTecnomarketEcSpider(scrapy.Spider):
    name = "ecuador_tecnomarket_ec"
    allowed_domains = ["tecnomarket.ec"]
    currency = "USD"
    language = "es"
    start_url = "https://tecnomarket.ec/"

    async def start(self):
        yield scrapy.Request(self.start_url, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("product-card.card--product"):
            product_id = card.attrib.get("data-product-id")
            link = card.css(".card__title a")
            name = " ".join(link.css("::text").getall()).strip()
            href = link.attrib.get("href") if link else None
            value = " ".join(card.css(".price__current .js-value::text, .price__current .js-value sup::text").getall())
            match = re.search(r"\$\s*([\d,]+)(?:\s+(\d{2}))?", value)
            category = " ".join(card.css(".card__vendor::text").getall()).strip()
            if not (product_id and name and href and match):
                continue
            amount = float(match.group(1).replace(",", "")) + (int(match.group(2) or "0") / 100)
            if amount <= 0:
                continue
            yield {
                "product_id": product_id, "product_name": name,
                "category": category or "consumer goods", "price": f"{amount:.2f}",
                "currency": self.currency, "available": True, "url": response.urljoin(href),
                "locality": "Ecuador", "language": self.language, "scraped_at_utc": scraped_at,
            }
