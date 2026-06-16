import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"([\d,.]+)")


class BruneianmadeSpider(scrapy.Spider):
    name = "bruneianmade"
    allowed_domains = ["bruneianmade.com", "www.bruneianmade.com"]
    currency = "BND"
    language = "en"

    SELECTORS = {
        "products": "li.product.type-product",
        "product_name": "h2.woocommerce-loop-product__title::text",
        "price": "span.price .woocommerce-Price-amount bdi",
        "link": "a.woocommerce-LoopProduct-link::attr(href)",
        "next_page": "a.next.page-numbers::attr(href)",
    }

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 3,
    }

    async def start(self):
        yield scrapy.Request(
            "https://bruneianmade.com/shop/",
            callback=self.parse_listing,
        )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()

        for product in response.css(self.SELECTORS["products"]):
            name = product.css(self.SELECTORS["product_name"]).get()
            if not name:
                continue

            price_node = product.css(self.SELECTORS["price"])
            texts = [
                t.strip()
                for t in price_node.css("::text").getall()
                if t.strip() and t.strip() != "BND"
            ]
            price_text = "".join(texts)
            m = PRICE_RE.search(price_text.replace(",", ""))
            if not m:
                logger.debug(f"no price for {name}")
                continue

            href = product.css(self.SELECTORS["link"]).get() or ""
            product_id = href.rstrip("/").rsplit("/", 1)[-1] if href else None

            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": None,
                "price": m.group(1),
                "currency": self.currency,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        next_href = response.css(self.SELECTORS["next_page"]).get()
        if next_href:
            yield scrapy.Request(
                response.urljoin(next_href),
                callback=self.parse_listing,
            )
