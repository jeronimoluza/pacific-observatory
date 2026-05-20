"""
Spider for Long Chau (Vietnam pharmacy) - https://nhathuoclongchau.com.vn/
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class LongChauSpider(CrawlSpider):
    name = "long_chau"
    allowed_domains = ["nhathuoclongchau.com.vn"]
    start_urls = ["https://nhathuoclongchau.com.vn/thuc-pham-chuc-nang"]
    currency = "VND"

    SELECTORS = get_selectors("long_chau")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/[a-z0-9\-]+/[a-z0-9\-]+\.html$",
                deny=r"(gio-hang|dang-nhap|tim-kiem|cart|checkout|login|search|/bai-viet/|/benh/|/dich-vu-|/he-thong-|/khuyen-mai|/thuoc-mac/|/lien-he|/chinh-sach|/gioi-thieu|/tin-tuc|/cong-ty|/thong-tin|/danh-muc|/blog)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        if not response.url.endswith(".html"):
            return
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
