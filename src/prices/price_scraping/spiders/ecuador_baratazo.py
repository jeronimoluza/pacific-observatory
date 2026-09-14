import re
from datetime import datetime, timezone

import scrapy


class EcuadorBaratazoSpider(scrapy.Spider):
    name = "ecuador_baratazo"
    allowed_domains = ["baratazo.com", "www.baratazo.com"]
    currency = "USD"
    language = "es"
    start_url = "https://www.baratazo.com/"

    async def start(self):
        yield scrapy.Request(self.start_url, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("ul.products li.product"):
            product_id = card.attrib.get("class", "")
            post = re.search(r"post-(\d+)", product_id)
            link = card.css(".woocommerce-loop-product__title a")
            name = " ".join(link.css("::text").getall()).strip()
            href = link.attrib.get("href") if link else None
            current = card.css(".price ins .woocommerce-Price-amount::text, .price ins bdi::text")
            if not current:
                current = card.css(".price > .woocommerce-Price-amount bdi::text")
            price_text = "".join(current.getall())
            match = re.search(r"(\d+(?:\.\d{1,2})?)", price_text)
            category = " ".join(card.css(".product__categories a::text").getall()).strip()
            if not (post and name and href and match and float(match.group(1)) > 0):
                continue
            yield {
                "product_id": post.group(1), "product_name": name,
                "category": category or "consumer goods", "price": f"{float(match.group(1)):.2f}",
                "currency": self.currency, "available": True, "url": response.urljoin(href),
                "locality": "Quito, Ecuador", "language": self.language, "scraped_at_utc": scraped_at,
            }
