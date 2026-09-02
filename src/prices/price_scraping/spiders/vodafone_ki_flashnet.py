"""Vodafone Kiribati prepaid broadband tariff image."""

from __future__ import annotations

from datetime import datetime, timezone
import re

import scrapy


_SLUG_RE = re.compile(r"[^a-z0-9]+")

_PLANS = [
    ("Normal Plans", "2.00", "450MB", "2 days"),
    ("Normal Plans", "5.00", "950MB", "6 days"),
    ("Normal Plans", "6.00", "1.7GB", "6 days"),
    ("Normal Plans", "10.00", "2.7GB", "11 days"),
    ("Normal Plans", "20.00", "3.5GB", "20 days"),
    ("Normal Plans", "30.00", "5.7GB", "30 days"),
    ("Normal Plans", "50.00", "6.5GB", "30 days"),
    ("Biri mwaaka", "100.00", "11GB", "30 Days"),
    ("Biri mwaaka", "150.00", "16GB", "30 Days"),
    ("Biri mwaaka", "200.00", "22GB", "30 Days"),
    ("Biri mwaaka", "250.00", "27GB", "30 Days"),
    ("Biri mwaaka", "300.00", "33GB", "30 Days"),
    ("Biri mwaaka", "400.00", "44GB", "30 Days"),
]


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class VodafoneKiFlashnetSpider(scrapy.Spider):
    name = "vodafone_ki_flashnet"
    allowed_domains = ["vodafone.com.ki", "www.vodafone.com.ki"]
    start_urls = ["https://www.vodafone.com.ki/Services/Bundles/Flashnet-Wifi-Router"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        title = " ".join(response.css("title::text").getall())
        if "Flashnet" not in title and "Pocket Wifi" not in response.text:
            self.logger.warning("Unexpected Vodafone Kiribati Flashnet page")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for plan_group, price, allowance, validity in _PLANS:
            product_id = _slug(f"{plan_group}-{allowance}-{validity}-{price}")
            yield {
                "product_id": product_id,
                "product_name": (
                    f"Vodafone Kiribati {plan_group} prepaid broadband {allowance}"
                ),
                "category": "Prepaid broadband bundle",
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
