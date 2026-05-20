"""
Spider for Co.opmart Online (Vietnam) - https://cooponline.vn/
SSR site with /<slug>--s<digits> PDPs. CrawlSpider, no Playwright needed.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class CoopmartSpider(CrawlSpider):
    name = "coopmart"
    allowed_domains = ["cooponline.vn", "www.cooponline.vn"]
    start_urls = [
        "https://cooponline.vn/c/rau-cu-trai-cay",
        "https://cooponline.vn/c/thit-trung-hai-san",
        "https://cooponline.vn/c/sua-san-pham-tu-sua",
    ]
    currency = "VND"

    SELECTORS = get_selectors("coopmart")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"--s\d+",
                deny=r"(/gio-hang|/tai-khoan|/dang-nhap|/tin-tuc|/chinh-sach|/ky-niem-|/c/)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS.get("category", []), method="getall"
        )
        product_id = extractor.extract(
            "product_id", self.SELECTORS.get("product_id", [])
        )

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
