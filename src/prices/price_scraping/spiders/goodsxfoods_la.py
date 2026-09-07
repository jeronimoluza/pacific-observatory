"""
Spider for Goodsxfoods (Lao PDR) - https://www.goodsxfoods.com/

Goodsxfoods is a Vientiane wholesale/retail food supplier. The public Next.js
pages render product cards server-side, including product URLs, names, Kip
prices, and units. The site also shows some catalogue placeholders at ₭0; those
are quote/empty-price rows and are intentionally skipped.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

logger = logging.getLogger(__name__)


PRICE_RE = re.compile(r"₭\s*([\d,]+(?:\.\d+)?)")
UNIT_RE = re.compile(r"/\s*([A-Za-z][A-Za-z0-9_-]*)")


class GoodsxfoodsLaSpider(scrapy.Spider):
    name = "goodsxfoods_la"
    allowed_domains = ["goodsxfoods.com", "www.goodsxfoods.com"]
    currency = "LAK"
    language = "lo"

    start_urls = ["https://www.goodsxfoods.com/products"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        category_links = response.css('a[href^="/products?category="]::attr(href)').getall()
        for href in sorted(set(category_links)):
            yield response.follow(
                href,
                callback=self.parse_listing,
                meta={"category_slug": href.rsplit("category=", 1)[-1]},
            )

        yield from self.parse_listing(response)

    def parse_listing(self, response):
        category_slug = response.meta.get("category_slug")
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in response.css('a[href^="/products/"]'):
            href = card.attrib.get("href") or ""
            path = urlparse(href).path
            if not path.startswith("/products/"):
                continue

            texts = [t.strip() for t in card.css("::text").getall() if t.strip()]
            joined = " ".join(texts)
            price_match = PRICE_RE.search(joined)
            if not price_match:
                continue

            price_text = price_match.group(1).replace(",", "")
            try:
                price_value = float(price_text)
            except ValueError:
                continue
            if price_value <= 0:
                continue

            name = card.css("p.line-clamp-2::text").get()
            if not name:
                name = card.css("img::attr(alt)").get()
            if not name:
                continue
            name = " ".join(name.split())

            unit_match = UNIT_RE.search(joined)
            unit = unit_match.group(1) if unit_match else None
            category = category_slug.replace("-", " ") if category_slug else None
            product_id = path.rstrip("/").rsplit("/", 1)[-1]

            yield {
                "product_id": product_id,
                "product_name": f"{name} ({unit})" if unit else name,
                "price": str(int(price_value)) if price_value.is_integer() else str(price_value),
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(path),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            logger.info("Scraped product: %s", name)
