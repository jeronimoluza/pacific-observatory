import re
import logging
from scrapy.spiders import Spider

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"HK\$(\d+)")


class HkcslPrepaidSpider(Spider):
    name = "hkcsl_prepaid"
    allowed_domains = ["www.hkcsl.com"]
    start_urls = ["https://www.hkcsl.com/en/prepaid/"]
    currency = "HKD"
    language = "en"

    SELECTORS = {
        "card": "div.swiper-slide",
        "product_name": "div.title-box::text",
        "price_text": "span.small-tetx::text",
        "detail_url": "a.learn-more::attr(href)",
    }

    def parse(self, response):
        cards = response.css(self.SELECTORS["card"])
        logger.info("Found %d swiper-slide cards on %s", len(cards), response.url)
        for card in cards:
            name_parts = card.css(self.SELECTORS["product_name"]).getall()
            product_name = " ".join(p.strip() for p in name_parts if p.strip()) or None

            price_text = card.css(self.SELECTORS["price_text"]).get(default="")
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price = m.group(1)

            detail_url = card.css(self.SELECTORS["detail_url"]).get()
            if detail_url and not detail_url.startswith("http"):
                detail_url = response.urljoin(detail_url)

            if product_name and price:
                yield {
                    "product_name": product_name,
                    "price": price,
                    "currency": self.currency,
                    "url": detail_url or response.url,
                    "language": self.language,
                }
