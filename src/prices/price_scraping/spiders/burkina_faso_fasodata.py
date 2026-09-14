"""Scrape FasoData's public latest food-price endpoint for Burkina Faso."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


API_URL = (
    "https://fasodata.com/api/prices/latest"
    "?region=National&country=BFA&sources=wfp"
)
COMMODITY_NAMES = {
    "cowpea": "Cowpea (niebe)",
    "groundnut": "Groundnuts (shelled)",
    "maize": "Maize (white)",
    "millet": "Millet",
    "rice_imported": "Rice (imported)",
    "rice_local": "Rice (local)",
    "sorghum": "Sorghum (white)",
}


def clean(value):
    return " ".join(str(value or "").split())


def parse_price_records(payload, source_url=API_URL, scraped_at=None):
    """Yield valid, dated, positive-price food observations."""
    if not isinstance(payload, list):
        return
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen = set()
    for record in payload:
        if not isinstance(record, dict):
            continue
        record_id = clean(record.get("id"))
        commodity = clean(record.get("commodity"))
        location = clean(record.get("market") or record.get("region"))
        unit = clean(record.get("unit"))
        price_date = clean(record.get("price_date"))
        try:
            price = Decimal(str(record.get("price")))
            date.fromisoformat(price_date)
        except (InvalidOperation, TypeError, ValueError):
            continue
        if (
            not record_id
            or record_id in seen
            or not commodity
            or not location
            or not unit
            or price <= 0
        ):
            continue
        seen.add(record_id)
        product_name = COMMODITY_NAMES.get(commodity, commodity.replace("_", " ").title())
        yield {
            "product_id": record_id,
            "product_name": product_name,
            "category": "food commodity",
            "price": format(price, "f"),
            "currency": "XOF",
            "country": "Burkina Faso",
            "sector": "consumer_goods",
            "available": True,
            "url": f"{source_url}#record-{record_id}",
            "language": "fr",
            "observation_date": price_date,
            "location": location,
            "unit": unit,
            "source": clean(record.get("source")),
            "quality": clean(record.get("quality")),
            "n_observations": record.get("n_obs"),
            "scraped_at_utc": scraped_at,
        }


class BurkinaFasoFasoDataSpider(scrapy.Spider):
    name = "burkina_faso_fasodata"
    allowed_domains = ["fasodata.com"]
    start_urls = [API_URL]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://fasodata.com/carte-prix",
        },
    }

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        yield from parse_price_records(payload, source_url=response.url)
