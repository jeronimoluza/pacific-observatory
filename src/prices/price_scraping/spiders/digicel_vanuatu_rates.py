"""Digicel Vanuatu prepaid and postpaid rate tables."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"VTU?\s*([0-9]+(?:\.[0-9]+)?)", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class DigicelVanuatuRatesSpider(scrapy.Spider):
    name = "digicel_vanuatu_rates"
    allowed_domains = ["digicelpacific.com", "www.digicelpacific.com"]
    start_urls = ["https://www.digicelpacific.com/mobile/vu/rates"]
    currency = "VUV"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        table_labels = {
            0: "Prepaid Rates (VIP)",
            1: "Postpaid Rate (VEP)",
        }
        seen = set()

        for table_index, table in enumerate(response.css("table")):
            if table_index > 1:
                break
            rows = table.css("tr")
            if not rows:
                continue
            headers = [
                _clean(" ".join(cell.css("::text").getall()))
                for cell in rows[0].css("th, td")
            ]
            if "Rate" not in headers:
                continue
            label = table_labels.get(table_index, f"Rate table {table_index + 1}")
            for row in rows[1:]:
                cells = [
                    _clean(" ".join(cell.css("::text").getall()))
                    for cell in row.css("td")
                ]
                if len(cells) != len(headers):
                    continue
                values = dict(zip(headers, cells))
                price_match = _PRICE_RE.search(values.get("Rate") or "")
                if not price_match:
                    continue

                service = values.get("Service Type") or "Service"
                rate_type = values.get("Rate Type") or "Rate"
                unit = values.get("Unit") or None
                product_name = f"Digicel Vanuatu {label} {service} {rate_type}"
                if unit:
                    product_name = f"{product_name} ({unit})"
                key = (label, service, rate_type, unit, price_match.group(1))
                if key in seen:
                    continue
                seen.add(key)
                product_id = _slug("-".join(str(part) for part in key if part))

                yield {
                    "product_id": product_id,
                    "product_name": product_name[:500],
                    "category": label,
                    "price": price_match.group(1),
                    "price_text": values.get("Rate"),
                    "currency": self.currency,
                    "available": True,
                    "unit": unit,
                    "charging": values.get("Charging") or None,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
