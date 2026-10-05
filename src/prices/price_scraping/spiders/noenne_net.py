"""Public apparel catalogue for Nønne, Nuuk, Greenland."""

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"DKK\s*([\d.]+(?:,\d{2})?)", re.I)


def parse_dkk(text):
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    return match.group(1).replace(".", "").replace(",", ".")


class NoenneNetSpider(scrapy.Spider):
    name = "noenne_net"
    allowed_domains = ["noenne.net", "www.noenne.net"]
    start_urls = ["https://www.noenne.net/varekatalog?p=1"]

    def parse(self, response):
        seen = set()
        for href in response.css('a[href*="/vare/"]::attr(href)').getall():
            url = response.urljoin(href)
            if url not in seen:
                seen.add(url)
                yield response.follow(url, self.parse_product)

        for href in response.css('a[href*="varekatalog?p="]::attr(href)').getall():
            yield response.follow(href, self.parse)

    def parse_product(self, response):
        name = response.css("h1::text").get(default="").strip()
        main = response.css("main").xpath("string(.)").get() or response.xpath("string(//body)").get()
        price = parse_dkk(main)
        if not name or price is None:
            return
        stock_text = " ".join(response.xpath("//body//text()").getall()).lower()
        yield {
            "product_name": name,
            "price": price,
            "currency": "DKK",
            "available": "udsolgt" not in stock_text,
            "url": response.url,
            "language": "da",
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
