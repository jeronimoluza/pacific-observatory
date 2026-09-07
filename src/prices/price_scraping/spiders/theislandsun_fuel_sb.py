"""Solomon Islands fuel-price bulletin reported by The Island Sun."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

import scrapy


def _clean(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).replace("\xa0", " ").split())


class TheIslandSunFuelSbSpider(scrapy.Spider):
    name = "theislandsun_fuel_sb"
    allowed_domains = ["theislandsun.com.sb", "www.theislandsun.com.sb"]
    start_urls = ["https://theislandsun.com.sb/new-fuel-prices-take-effect/"]
    currency = "SBD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        text = _clean(
            " ".join(
                response.xpath("//body//text()[not(ancestor::script) and not(ancestor::style)]").getall()
            )
        )
        rows = []
        rows.extend(
            self._fuel_triplet(
                text,
                r"new prices are \$([0-9.]+) per litre for petrol, \$([0-9.]+) for diesel and \$([0-9.]+) for kerosene",
                "Retail fuel, Honiara service stations, {fuel}, per litre",
            )
        )
        rows.extend(
            self._fuel_triplet(
                text,
                r"For bulk purchases, petrol is priced at \$([0-9.]+) per litre, while diesel is \$([0-9.]+) and kerosene \$([0-9.]+)",
                "Bulk fuel, Honiara, {fuel}, per litre",
            )
        )
        rows.extend(
            self._fuel_triplet(
                text,
                r"200-litre drums, including GST, at \$([0-9,]+\.[0-9]{2}) for petrol, \$([0-9,]+\.[0-9]{2}) for diesel and \$([0-9,]+\.[0-9]{2}) for kerosene",
                "Fuel refill, 200-litre drum including GST, {fuel}",
            )
        )
        rows.extend(
            self._fuel_triplet(
                text,
                r"200-litre refill with a new drum is listed at \$([0-9,]+\.[0-9]{2}) for petrol, \$([0-9,]+\.[0-9]{2}) for diesel and \$([0-9,]+\.[0-9]{2}) for kerosene",
                "Fuel refill with new 200-litre drum, {fuel}",
            )
        )

        for name, price in rows:
            price = price.rstrip(".")
            product_id = hashlib.sha1(f"{name}|{price}".encode("utf-8")).hexdigest()[:16]
            yield {
                "product_id": product_id,
                "product_name": name,
                "category": "Fuel",
                "price": price.replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _fuel_triplet(text: str, pattern: str, name_template: str) -> list[tuple[str, str]]:
        match = re.search(pattern, text, re.I)
        if not match:
            return []
        fuels = ["petrol", "diesel", "kerosene"]
        return [(name_template.format(fuel=fuel), price) for fuel, price in zip(fuels, match.groups())]
