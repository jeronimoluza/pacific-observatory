import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"(?:؋|AFN)\s*([0-9][0-9,.]*)", re.I)


class JamshidiMartSpider(scrapy.Spider):
    name = "jamshidi_mart"
    allowed_domains = ["jamshidimart.com", "www.jamshidimart.com"]
    start_urls = [
        "https://jamshidimart.com/product-category/snacks-cookies/beverages/soft-drink/?sale_status=1"
    ]

    def parse(self, response):
        for card in response.css("li.product, .product.type-product"):
            href = card.css("a.woocommerce-LoopProduct-link::attr(href), a[href*='/product/']::attr(href)").get()
            name = card.css(".woocommerce-loop-product__title::text, h2::text, h3::text").get()
            prices = PRICE_RE.findall(" ".join(card.xpath(".//text()").getall()))
            if href and name and prices:
                yield {"product_name": " ".join(name.split()), "price": prices[0].replace(",", ""), "currency": "AFN", "available": "outofstock" not in (card.attrib.get("class") or ""), "url": response.urljoin(href), "language": "en", "scraped_at_utc": datetime.now(timezone.utc).isoformat()}
        nxt = response.css("a.next.page-numbers::attr(href)").get()
        if nxt:
            yield response.follow(nxt, self.parse)

