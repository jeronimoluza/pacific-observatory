"""
Spider for scraping OTW (Timor-Leste food delivery, Dili) - https://otw-tl.com/
Discovers restaurants via the /load-more-restorantes/ AJAX endpoint (returns
an HTML fragment inside a JSON envelope), then scrapes each restaurant's menu
page for item name, category, and price.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class OtwTlSpider(scrapy.Spider):
    """Spider for OTW food delivery (Dili, Timor-Leste)."""

    name = "otw_tl"
    allowed_domains = ["otw-tl.com"]
    currency = "USD"

    LISTING_URL = "https://otw-tl.com/load-more-restorantes/?kategoriaproduto=comida&page={page}"

    def start_requests(self):
        yield scrapy.Request(
            self.LISTING_URL.format(page=1),
            callback=self.parse_restaurant_list,
            meta={"page": 1},
        )

    def parse_restaurant_list(self, response):
        page = response.meta["page"]
        try:
            data = json.loads(response.text)
        except ValueError:
            logger.warning(f"Non-JSON response on listing page {page}")
            return

        html = data.get("html") or ""
        if not html.strip():
            logger.info(f"Listing exhausted at page {page}")
            return

        fragment = scrapy.Selector(text=html)
        hrefs = fragment.css("a::attr(href)").getall()
        restaurant_urls = sorted(
            set(h for h in hrefs if h and "/restorante/" in h)
        )
        for href in restaurant_urls:
            yield response.follow(href, callback=self.parse_restaurant)

        yield scrapy.Request(
            self.LISTING_URL.format(page=page + 1),
            callback=self.parse_restaurant_list,
            meta={"page": page + 1},
        )

    def parse_restaurant(self, response):
        items = response.css("div.product-item")
        if not items:
            logger.warning(f"No menu items found on {response.url}")
            return

        for idx, item in enumerate(items):
            product_name = item.css("h6::text").get()
            category = item.css("p.text-muted::text").get()
            price_text = item.css("span.text-primary::text").get()

            if product_name and price_text:
                yield {
                    "product_name": product_name.strip(),
                    "category": category.strip() if category else None,
                    "price": price_text.replace("$", "").strip(),
                    "currency": self.currency,
                    # Fragment keeps each menu item's URL unique - one restaurant
                    # page yields many items, and DuplicationPipeline dedups on
                    # item['url'] (see prices_duplication_pipeline_url_dedup_bug).
                    "url": f"{response.url}#{idx}",
                    "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
                }
