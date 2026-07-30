"""
Spider for Khanburgedei eFoods (Mongolia) - https://efoods.khanburgedei.mn/

Khanburgedei is a premium Mongolian supermarket chain (TTEM LLC, ~8 stores).
Its dedicated grocery storefront (efoods.khanburgedei.mn, separate from the
general-merchandise estore.khanburgedei.mn) is server-rendered HTML
(Tier 1A) built on the Greensoft shop theme. Product listing pages
(/products?category_id=...) render product cards directly in HTML with a
clean numeric price in a data attribute — no need to visit individual
/product/{id} detail pages.

Crawl is restricted to food-relevant department roots via category_root:
  9204 = Өдөр тутмын хүнс (daily food: bread, meat, dairy)
  9209 = Жимс, хүнсний ногоо (fruit & vegetables)
  9213 = Боловсруулсан хүнс (processed food: flour, cereal, oil, tea/coffee, canned)
  9233 = Шингэн хүнс (liquid food: water, juice, alcohol)
  9223 = Амттан (sweets: chocolate, candy, ice cream)
  9237 = Хөлдөөсөн бүтээгдэхүүн (frozen products)
"""

import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

_FOOD_ROOTS = ("9204", "9209", "9213", "9233", "9223", "9237")


class KhanburgedeiEfoodsSpider(CrawlSpider):
    name = "khanburgedei_efoods"
    allowed_domains = ["efoods.khanburgedei.mn"]
    start_urls = [
        f"https://efoods.khanburgedei.mn/products?category_id={root}&category_root={root}"
        for root in _FOOD_ROOTS
    ]
    currency = "MNT"

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/products\?category_id=\d+&category_root=(?:%s)"
                % "|".join(_FOOD_ROOTS),
                deny=r"(/cart|/checkout|/login|/register|/account|/wishlist)",
            ),
            callback="parse_listing",
            follow=True,
        ),
    )

    def parse_listing(self, response):
        cards = response.css("div.product-card")
        if not cards:
            return

        for card in cards:
            product_name = card.css("div.product-card__name a::text").get()
            product_url = card.css("div.product-card__name a::attr(href)").get()
            price = card.css("a[data-ct-price]::attr(data-ct-price)").get()
            product_id = card.css("a[data-ct-id]::attr(data-ct-id)").get()
            category_parts = card.css("div.product-cat-title::text").getall()
            category = (
                " > ".join(p.strip() for p in category_parts if p.strip())
                if category_parts
                else None
            )

            if not product_name or not price:
                continue

            product_name = re.sub(r"\s+", " ", product_name).strip()

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(product_url) if product_url else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
