"""ASIAPRESS DPRK market price index table."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_DATE_RE = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})")
_PRICE_RE = re.compile(r"([\d,]+)\s*Won", re.I)
_ITEMS = {
    1: ("gasoline", "Gasoline", "Fuel", "kg"),
    2: ("diesel_oil", "Diesel Oil", "Fuel", "kg"),
    3: ("rice", "Rice", "Food staples", "kg"),
    4: ("corn", "Corn", "Food staples", "kg"),
}
_MAX_OBSERVATION_DATES = 20


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _parse_date(text: str) -> str | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    month_name, day, year = match.groups()
    month = _MONTHS.get(month_name.lower().rstrip("."))
    if not month:
        return None
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"


def _parse_price(text: str) -> str | None:
    match = _PRICE_RE.search(text)
    if not match:
        return None
    return match.group(1).replace(",", "")


class AsiapressKpMarketSpider(scrapy.Spider):
    name = "asiapress_kp_market"
    allowed_domains = ["asiapress.org", "www.asiapress.org"]
    start_urls = ["https://www.asiapress.org/rimjin-gang/north-k-korea-prices/"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        dates_seen = 0
        for row in response.css("#tablepress-1 tbody tr"):
            cells = row.css("td")
            if len(cells) < 5:
                continue
            date_text = _clean(" ".join(cells[0].css("::text").getall()))
            observation_date = _parse_date(date_text)
            if not observation_date:
                continue
            if dates_seen >= _MAX_OBSERVATION_DATES:
                break
            dates_seen += 1
            for index, (slug, item_name, category, unit) in _ITEMS.items():
                price = _parse_price(
                    _clean(" ".join(cells[index].css("::text").getall()))
                )
                if not price:
                    continue
                product_id = f"{observation_date}:{slug}"
                yield {
                    "product_id": product_id,
                    "product_name": item_name,
                    "category": category,
                    "price": price,
                    "currency": "KPW",
                    "available": True,
                    "unit": unit,
                    "observation_date": observation_date,
                    "url": f"{response.url}#{product_id}",
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }
