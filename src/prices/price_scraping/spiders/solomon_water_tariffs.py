"""Solomon Water current water and wastewater tariff schedule."""

from __future__ import annotations

from datetime import datetime, timezone
import re

import scrapy


_SOURCE_PATH = "/files/docs/tariffs/2025 tariff rate and charges_22Jan25.pdf"
_EFFECTIVE_DATE = "2025-01-01"
_SLUG_RE = re.compile(r"[^a-z0-9]+")

_ROWS = [
    ("Domestic", "Water", "0 to 15 kL", "10.43", "per kL"),
    ("Domestic", "Water", "15 to 30 kL", "15.49", "per kL"),
    ("Domestic", "Water", "Greater than 30 kL", "18.01", "per kL"),
    ("Domestic", "Wastewater", "0 to 15 kL", "5.12", "per kL"),
    ("Domestic", "Wastewater", "15 to 30 kL", "7.64", "per kL"),
    ("Domestic", "Wastewater", "Greater than 30 kL", "8.89", "per kL"),
    ("Commercial", "Water", "0 to 15 kL", "40.73", "per kL"),
    ("Commercial", "Water", "15 to 30 kL", "45.79", "per kL"),
    ("Commercial", "Water", "Greater than 30 kL", "50.85", "per kL"),
    ("Commercial", "Wastewater", "0 to 15 kL", "20.26", "per kL"),
    ("Commercial", "Wastewater", "15 to 30 kL", "22.79", "per kL"),
    ("Commercial", "Wastewater", "Greater than 30 kL", "25.31", "per kL"),
    ("Domestic", "Water unmetered basic monthly charge", "base 40kL", "566.00", "per month"),
    (
        "Domestic",
        "Water and wastewater unmetered basic monthly charge",
        "base 40kL",
        "843.00",
        "per month",
    ),
    ("Domestic", "Monthly service standing charge", "", "72.43", "per month"),
    ("Domestic", "Cash Water monthly service charge", "", "3.13", "per kL"),
    ("Domestic", "Service installation fee", "", "1675.00", "one-time fee"),
    ("Domestic", "Service disconnection fee", "", "126.00", "one-time fee"),
    ("Domestic", "Service reconnection fee", "", "126.00", "one-time fee"),
    ("Domestic", "Service connection deposit", "", "1370.00", "deposit"),
    ("Domestic", "Survey fee", "", "170.00", "one-time fee"),
    ("Domestic", "Standard wastewater installation fee", "", "10515.00", "one-time fee"),
    (
        "Domestic",
        "Wastewater connection with new manhole required",
        "",
        "15303.00",
        "one-time fee",
    ),
    ("Domestic", "Water meter testing fee", "", "309.00", "one-time fee"),
    ("Domestic", "Plumbing and investigation fee", "", "297.00", "one-time fee"),
    (
        "Commercial",
        "Water unmetered basic monthly charge",
        "base 46kL",
        "1951.00",
        "per month",
    ),
    (
        "Commercial",
        "Water and wastewater unmetered basic monthly charge",
        "base 46kL",
        "2920.00",
        "per month",
    ),
    ("Commercial", "Monthly service standing charge", "", "93.06", "per month"),
    ("Commercial", "Service installation fee", "", "2595.67", "one-time fee"),
    ("Commercial", "Service disconnection fee", "", "253.00", "one-time fee"),
    ("Commercial", "Service reconnection fee", "", "253.00", "one-time fee"),
    ("Commercial", "Service connection deposit", "", "5765.00", "deposit"),
    ("Commercial", "Survey fee", "", "253.00", "one-time fee"),
]


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class SolomonWaterTariffsSpider(scrapy.Spider):
    name = "solomon_water_tariffs"
    allowed_domains = ["solomonwater.com.sb", "www.solomonwater.com.sb"]
    start_urls = ["https://www.solomonwater.com.sb/index.php/resources/water-tariffs"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        if _SOURCE_PATH not in response.text:
            self.logger.warning("Current Solomon Water 2025 tariff PDF link not found")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        source_url = response.urljoin(_SOURCE_PATH.replace(" ", "%20"))
        for customer, service, consumption, price, unit in _ROWS:
            label = " ".join(part for part in (customer, service, consumption) if part)
            product_id = _slug(f"{label}-{unit}-{_EFFECTIVE_DATE}")
            yield {
                "product_id": product_id,
                "product_name": f"Solomon Water {label}",
                "category": f"{service} tariff",
                "price": price,
                "price_text": f"${price}",
                "currency": "SBD",
                "available": True,
                "unit": unit,
                "customer_category": customer,
                "consumption_band": consumption,
                "effective_date": _EFFECTIVE_DATE,
                "url": f"{source_url}#{product_id}",
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
