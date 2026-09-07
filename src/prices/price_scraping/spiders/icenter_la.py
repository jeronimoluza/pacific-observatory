"""Spider for iCenter Lao."""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.icenter.com.la"
PRODUCT_RE = re.compile(
    r'\{\\"id\\":\\"(?P<id>[^\\"]+)\\"'
    r'(?:(?!\{\\"id\\":).)*?\\"sku\\":\\"(?P<sku>[^\\"]*)\\"'
    r'(?:(?!\{\\"id\\":).)*?\\"brand\\":(?P<brand>null|\\".*?\\")'
    r'(?:(?!\{\\"id\\":).)*?\\"category\\":\\"(?P<category>[^\\"]*)\\"'
    r'(?:(?!\{\\"id\\":).)*?\\"status\\":\\"(?P<status>[^\\"]*)\\"'
    r'(?:(?!\{\\"id\\":).)*?\\"priceLak\\":(?P<price_lak>\d+)'
    r'(?:(?!\{\\"id\\":).)*?\\"nameEn\\":\\"(?P<name>.*?)\\"'
    r'(?:(?!\{\\"id\\":).)*?\\"shortEn\\":\\"(?P<short>.*?)\\"'
    r'(?:(?!\{\\"id\\":).)*?\\"stockQty\\":(?P<stock>\d+)',
    re.S,
)


def _json_string(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('\\"') and value.endswith('\\"'):
        value = value[2:-2]
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


class IcenterLaSpider(scrapy.Spider):
    name = "icenter_la"
    allowed_domains = ["icenter.com.la", "www.icenter.com.la"]
    currency = "LAK"
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
        yield scrapy.Request(BASE_URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        count = 0
        for match in PRODUCT_RE.finditer(response.text):
            row = match.groupdict()
            product_id = row["id"]
            if product_id in seen:
                continue
            seen.add(product_id)
            name = _json_string(row["name"])
            if not name:
                name = _json_string(row["short"])
            if not name:
                continue
            count += 1
            yield {
                "product_id": row["sku"] or product_id,
                "product_name": name[:500],
                "brand": _json_string(row["brand"]) or None,
                "category": _json_string(row["category"]) or None,
                "price": row["price_lak"],
                "currency": self.currency,
                "available": int(row["stock"]) > 0,
                "url": response.urljoin(f"/product/{product_id}"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"icenter_la count={count} url={response.url}")
