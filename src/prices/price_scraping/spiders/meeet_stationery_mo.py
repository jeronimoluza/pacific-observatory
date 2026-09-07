"""MEEET Macao stationery Odoo shop catalog."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class MeeetStationeryMoSpider(scrapy.Spider):
    name = "meeet_stationery_mo"
    allowed_domains = ["shop.meeetmacau.com"]
    start_urls = [
        "https://shop.meeetmacau.com/shop/category/meeet-macau-by-product-type-stationery-208"
    ]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in response.css("td.oe_product"):
            name = product.css('a[itemprop="name"]::text').get()
            href = product.css('a[itemprop="name"]::attr(href)').get()
            price = product.css('span[itemprop="price"]::text').get()
            product_id = product.css('input[name="product_id"]::attr(value)').get()
            if not name or not href or not price:
                continue
            yield {
                "product_id": product_id or urljoin(response.url, href),
                "product_name": name.strip()[:500],
                "category": "Stationery",
                "price": price.strip(),
                "currency": "MOP",
                "available": True,
                "url": urljoin(response.url, href),
                "language": "zh-Hant",
                "scraped_at_utc": scraped_at,
            }

        next_href = response.css("ul.pagination li.next a::attr(href)").get()
        if next_href:
            yield response.follow(next_href, callback=self.parse)
