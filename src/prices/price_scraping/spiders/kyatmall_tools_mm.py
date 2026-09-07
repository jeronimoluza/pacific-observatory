"""Spider for KYATmall tools and hardware (Myanmar)."""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kyatmall.com"
START_URL = f"{BASE_URL}/list_tools_hardware.html"
PRODUCT_ID_RE = re.compile(r"/product/([0-9]+)\.html")


class KyatmallToolsMmSpider(scrapy.Spider):
    name = "kyatmall_tools_mm"
    allowed_domains = ["kyatmall.com", "www.kyatmall.com"]
    currency = "MMK"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for card in response.css("a.group[href*='/product/']"):
            href = card.attrib.get("href") or ""
            name = " ".join(card.css("h3::text").get("").split())
            price_text = card.css(".price-text::text").get() or ""
            price = re.search(r"[\d,]+(?:\.\d+)?", price_text)
            if not name or not price:
                continue
            product_id = PRODUCT_ID_RE.search(href)
            count += 1
            yield {
                "product_id": product_id.group(1) if product_id else None,
                "product_name": name[:500],
                "brand": None,
                "category": "tools hardware",
                "price": price.group(0).replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"kyatmall_tools_mm count={count} url={response.url}")
