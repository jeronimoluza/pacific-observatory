import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"([0-9][0-9,.]*)\s*AFN", re.I)


class HamachizSpider(scrapy.Spider):
    name = "hamachiz"
    allowed_domains = ["hamachiz.com", "www.hamachiz.com"]
    start_urls = ["https://www.hamachiz.com/collections/snacks"]

    def parse(self, response):
        for href in response.css('a[href*="/products/"]::attr(href)').getall():
            yield response.follow(response.urljoin(href), self.parse_product)
        next_page = response.css('a[rel="next"]::attr(href), a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_product(self, response):
        name = response.css("h1::text, h1 *::text").get()
        text = " ".join(response.xpath("//main//text() | //body//text()").getall())
        prices = PRICE_RE.findall(text)
        if not name or not prices:
            return
        yield {
            "product_name": " ".join(name.split()),
            "price": prices[0].replace(",", ""),
            "currency": "AFN",
            "available": not bool(response.css(".sold-out, .out-of-stock")),
            "url": response.url,
            "language": "en",
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
