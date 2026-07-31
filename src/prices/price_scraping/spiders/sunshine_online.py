"""
Spider for Sunshine Online (Malaysia) - https://sunshineonline.com.my/ssq/

OpenCart-based supermarket catalogue. Product name + price are present
directly in server-rendered category listing HTML, so this spider scrapes
listing pages only (no PDP visits needed). Category URLs are discovered
dynamically from the home page nav, then each category is paginated via
the "next" link in the OpenCart pagination widget.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://sunshineonline.com.my/ssq/"


class SunshineOnlineSpider(scrapy.Spider):
    name = "sunshine_online"
    allowed_domains = ["sunshineonline.com.my"]
    start_urls = [BASE_URL]
    currency = "MYR"

    def parse(self, response):
        category_links = set(
            response.css('a[href*="product/category"]::attr(href)').getall()
        )
        logger.info(f"Found {len(category_links)} category links")
        for link in category_links:
            yield scrapy.Request(link, callback=self.parse_category)

    def parse_category(self, response):
        breadcrumb = response.css("ul.breadcrumb li a::text").getall()
        category = breadcrumb[-1].strip() if breadcrumb else None

        cards = response.css("div.product-thumb")
        for card in cards:
            name = card.css("div.name a::text").get()
            url = card.css("div.name a::attr(href)").get()
            price = card.css("div.price span.price-new::text").get()
            if not price:
                price = card.css("div.price span.price-normal::text").get()

            if not name or not price:
                continue

            product_id = None
            if url:
                m = re.search(r"product_id=(\d+)", url)
                if m:
                    product_id = m.group(1)

            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": price.strip(),
                "currency": self.currency,
                "category": category,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            yield scrapy.Request(next_page, callback=self.parse_category)
