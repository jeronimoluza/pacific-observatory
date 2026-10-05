"""Scrape the first-party WooCommerce product cards from cigars.al."""

import html
import re
from datetime import datetime, timezone

import scrapy

_CARD_RE = re.compile(
    r'<div class="wd-product[^>]*?data-id="(?P<id>\d+)".*?'
    r'<h3 class="wd-entities-title"><a href="(?P<url>[^"]+)">(?P<name>[^<]+)</a></h3>.*?'
    r'<span class="price">.*?<bdi>(?P<price>.*?)&nbsp;.*?'
    r'currencySymbol[^>]*>(?P<symbol>[^<]+)</span>', re.S | re.I
)


def _amount(raw):
    value = re.sub(r"[^0-9.]", "", html.unescape(raw))
    return value if value and float(value) > 0 else None


class AlbaniaCigarsAlSpider(scrapy.Spider):
    name = "albania_cigars_al"
    allowed_domains = ["cigars.al"]
    currency = "ALL"
    language = "en"
    start_urls = ["https://cigars.al/shop/"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        seen = set()
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = list(_CARD_RE.finditer(response.text))
        for match in cards:
            product_id = match.group("id")
            if product_id in seen or match.group("symbol").strip() != "L":
                continue
            price = _amount(match.group("price"))
            if not price:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": html.unescape(match.group("name")).strip(),
                "category": "tobacco_and_smoking_accessories",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(html.unescape(match.group("url"))),
                "locality": "Albania",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

