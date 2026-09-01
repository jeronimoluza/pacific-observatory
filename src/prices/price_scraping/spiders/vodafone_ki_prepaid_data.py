"""Vodafone Kiribati prepaid mobile data tariff image."""

from __future__ import annotations

from datetime import datetime, timezone
import re

import scrapy


_SLUG_RE = re.compile(r"[^a-z0-9]+")

_PLANS = [
    ("Daily", "2", "1GB", "24 Hours"),
    ("Daily", "3", "1.6GB", "24 Hours"),
    ("Daily", "4", "3GB", "24 Hours"),
    ("Weekly", "5", "1GB", "7 Days"),
    ("Weekly", "6", "3GB", "7 Days"),
    ("Weekly", "8", "6GB", "7 Days"),
    ("Weekly", "11", "8GB", "7 Days"),
    ("Monthly", "20", "6GB", "30 Days"),
    ("Monthly", "30", "16GB", "30 Days"),
    ("Monthly", "50", "11GB", "30 Days"),
]


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class VodafoneKiPrepaidDataSpider(scrapy.Spider):
    name = "vodafone_ki_prepaid_data"
    allowed_domains = ["vodafone.com.ki", "www.vodafone.com.ki"]
    start_urls = ["https://www.vodafone.com.ki/Services/Bundles/Mobile-Data"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        title = " ".join(response.css("title::text").getall())
        if "Mobile Data" not in title and "Mobile Data" not in response.text:
            self.logger.warning("Unexpected Vodafone Kiribati mobile data page")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for plan, price, allowance, validity in _PLANS:
            product_id = _slug(f"{plan}-{allowance}-{validity}-{price}")
            yield {
                "product_id": product_id,
                "product_name": f"Vodafone Kiribati {plan} prepaid data {allowance}",
                "category": "Prepaid mobile data bundle",
                "price": price,
                "price_text": f"${price}",
                "currency": "AUD",
                "available": True,
                "unit": validity,
                "data_allowance": allowance,
                "url": f"{response.url}#{product_id}",
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
