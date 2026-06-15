"""Spider for Khaivai (Lao e-commerce marketplace) — https://khaivai.com/

WooCommerce-variant platform. Product pages at /product/[lao-slug].
Category pages at /category/[slug]. Prices displayed as "LAK100,000"
in meta[property='og:price:amount'] — strip the "LAK" prefix before parsing.
"""

import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)

_LAK_RE = re.compile(r"LAK\s*([\d,]+)", re.IGNORECASE)


def _parse_lak_meta(raw: str) -> str | None:
    """Strip 'LAK' prefix from og:price:amount and return a numeric string."""
    if raw is None:
        return None
    m = _LAK_RE.match(raw.strip())
    if m:
        return m.group(1).replace(",", "")
    # Fallback: strip non-digits except commas
    cleaned = re.sub(r"[^\d,]", "", raw).replace(",", "")
    return cleaned if cleaned else None


class KhaivaiSpider(CrawlSpider):
    name = "khaivai"
    allowed_domains = ["khaivai.com"]
    start_urls = [
        "https://khaivai.com/category/pant-rmoep",
        "https://khaivai.com/category/suit-hkxtn",
        "https://khaivai.com/category/short-sleeve-kw08v",
        "https://khaivai.com/",
    ]
    currency = "LAK"

    SELECTORS = get_selectors("khaivai")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/product/[^/?#]+",
                deny=r"(cart|checkout|account|login|register|compare|wishlist|search)",
            ),
            callback="parse_product",
            follow=False,
        ),
        Rule(
            LinkExtractor(
                allow=r"/category/[^/?#]+",
                deny=r"(cart|checkout|login|register)",
            ),
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)

        # product_name: h1 with fw-600 class or og:title
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])

        # price: og:price:amount gives "LAK100,000" — strip prefix
        raw_price = extractor.extract("price", self.SELECTORS["price"])
        price = _parse_lak_meta(raw_price) if raw_price else None

        # product_id: hidden input[name='product_id']
        product_id = extractor.extract(
            "product_id", self.SELECTORS.get("product_id", [])
        )

        # category: category menu links (best available — no breadcrumb on PDP)
        category = extractor.extract(
            "category", self.SELECTORS.get("category", []), method="getall"
        )

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category)
                if isinstance(category, list)
                else category,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info("Scraped product: %s @ LAK %s", product_name, price)
        else:
            logger.warning("Could not extract product data from %s", response.url)
