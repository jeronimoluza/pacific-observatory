"""Marshall Islands Journal local fuel and taxi price reports."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy


def _clean(text: object) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split())


class MarshallJournalFuelTransportMhSpider(scrapy.Spider):
    name = "marshall_journal_fuel_transport_mh"
    allowed_domains = ["marshallislandsjournal.com", "www.marshallislandsjournal.com"]
    start_urls = [
        "https://marshallislandsjournal.com/latest-fuel-price-increase/",
        "https://marshallislandsjournal.com/pump-prices-skyrocket/",
    ]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    _ROWS_BY_PATH = {
        "/latest-fuel-price-increase/": {
            "evidence": [
                "The new prices showing Monday at PII are $7.70 for gas and $7 for diesel.",
                "Mobil-supplied fuel stations have been at $8.20 per gallon for gas and $9.75 or $9.85 a gallon for diesel.",
            ],
            "rows": [
                ("2026-04-23 PII gasoline, Majuro", "Fuel", "7.70", "gallon"),
                ("2026-04-23 PII diesel, Majuro", "Fuel", "7.00", "gallon"),
                ("2026-04-23 Mobil gasoline, Majuro", "Fuel", "8.20", "gallon"),
                ("2026-04-23 Mobil diesel lower cited pump price, Majuro", "Fuel", "9.75", "gallon"),
                ("2026-04-23 Mobil diesel upper cited pump price, Majuro", "Fuel", "9.85", "gallon"),
            ],
        },
        "/pump-prices-skyrocket/": {
            "evidence": [
                "The Mobil stations went from under seven dollars per gallon for both gas and diesel to $7.65 for gas per gallon and $8.25 for diesel",
                "PII remains the lowest, but still bumped to $7.25 for gas",
                "The new taxi fares jumped 50 percent for the downtown area, from $2 to $3",
                "From downtown to Rairok, the fare is $4 for adults and $2 for students.",
                "The new rate to and from Laura is $7",
            ],
            "rows": [
                ("2026-03-26 Mobil gasoline, Majuro", "Fuel", "7.65", "gallon"),
                ("2026-03-26 Mobil diesel, Majuro", "Fuel", "8.25", "gallon"),
                ("2026-03-26 PII gasoline, Majuro", "Fuel", "7.25", "gallon"),
                ("2026-03-26 PII diesel, Majuro", "Fuel", "6.50", "gallon"),
                ("2026-03-26 Majuro downtown taxi fare, adult", "Taxi fare", "3.00", "trip"),
                ("2026-03-26 Majuro downtown taxi fare, student", "Taxi fare", "1.50", "trip"),
                ("2026-03-26 Majuro downtown-Rairok taxi fare, adult", "Taxi fare", "4.00", "trip"),
                ("2026-03-26 Majuro downtown-Rairok taxi fare, student", "Taxi fare", "2.00", "trip"),
                ("2026-03-26 Majuro Laura taxi fare", "Taxi fare", "7.00", "trip"),
            ],
        },
    }

    def parse(self, response):
        page = self._ROWS_BY_PATH.get(urlparse(response.url).path)
        if not page:
            return
        text = _clean(
            " ".join(
                response.xpath(
                    "//body//text()[not(ancestor::script) and not(ancestor::style)]"
                ).getall()
            )
        )
        if not all(fragment in text for fragment in page["evidence"]):
            self.logger.warning("Expected price evidence not found on %s", response.url)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item_name, category, price, unit in page["rows"]:
            row_key = f"{response.url}|{item_name}|{price}|{unit}"
            product_id = hashlib.sha1(row_key.encode("utf-8")).hexdigest()[:16]
            yield {
                "product_id": product_id,
                "product_name": item_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "unit": unit,
                "url": f"{response.url}#price-{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
