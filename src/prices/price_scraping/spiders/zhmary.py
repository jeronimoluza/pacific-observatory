import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"([0-9][0-9,.]*)\s*AFN", re.I)


class ZhmarySpider(scrapy.Spider):
    name = "zhmary"
    allowed_domains = ["zhmary.com", "www.zhmary.com"]
    start_urls = ["https://www.zhmary.com/"]

    def parse(self, response):
        for card in response.css(".item-card"):
            name = " ".join(card.css(".item-info h3 ::text, .item-info h3::text").getall()).strip()
            price = PRICE_RE.search(" ".join(card.css(".current-price ::text, .current-price::text").getall()))
            vendor = " ".join(card.css(".item-store ::text, .item-store::text").getall()).strip()
            image_url = card.css(".item-image img::attr(src)").get()
            product_id = (image_url or "").rsplit("/", 1)[-1].split(".", 1)[0]
            if name and price and vendor and product_id:
                yield {
                    "product_id": product_id,
                    "product_name": name,
                    "price": price.group(1).replace(",", ""),
                    "currency": "AFN",
                    "store": vendor,
                    "zone": "Aino Maina",
                    "url": f"{response.url}#product-{product_id}",
                    "language": "en",
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
