"""Spider for MGD Mall Myanmar Food & Groceries category."""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import scrapy

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)")


class MgdmallMmSpider(scrapy.Spider):
    name = "mgdmall_mm"
    allowed_domains = ["mgdmall.com.mm", "www.mgdmall.com.mm"]
    currency = "MMK"
    language = "en"

    start_urls = [
        "https://mgdmall.com.mm/en/category/food-%26-groceries?category_id=12",
    ]

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
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for card in response.css('a[href*="/product/details/"]'):
            href = card.attrib.get("href")
            if not href:
                continue

            name = card.css("h3::text").get()
            if not name:
                continue
            name = " ".join(name.split())

            price_text = " ".join(t.strip() for t in card.css("span::text").getall() if t.strip())
            if "Ks" not in price_text:
                continue

            price_match = PRICE_RE.search(price_text)
            if not price_match:
                continue
            price = price_match.group(1).replace(",", "")

            parsed = urlparse(href)
            product_id = (parse_qs(parsed.query).get("product_id") or [None])[0]
            product_id = product_id or parsed.path.rstrip("/").rsplit("/", 1)[-1]
            if product_id in seen:
                continue
            seen.add(product_id)

            yield {
                "product_id": str(product_id),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": "Food Groceries",
                "url": response.urljoin(href),
                "language": self.language,
                "store": "MGD Mall",
                "scraped_at_utc": scraped_at,
            }
            logger.info("Scraped product: %s", name)
