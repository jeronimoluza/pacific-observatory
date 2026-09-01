"""Vodafone Kiribati postpaid mobile tariff tables."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class VodafoneKiMobileSpider(scrapy.Spider):
    name = "vodafone_ki_mobile"
    allowed_domains = ["vodafone.com.ki", "www.vodafone.com.ki"]
    start_urls = ["https://www.vodafone.com.ki/Services/Postpaid-Plan/Mobile"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for table_index, table in enumerate(response.css(".welcome-to-educa table")):
            rows = table.css("tr")
            if not rows:
                continue
            headers = [
                _clean(" ".join(cell.css("::text").getall()))
                for cell in rows[0].css("td, th")
            ]
            is_reload = any("reload" in h.lower() for h in headers)
            for row in rows[1:]:
                cells = [
                    _clean(" ".join(cell.css("::text").getall()))
                    for cell in row.css("td")
                ]
                if len(cells) < 3:
                    continue
                name, price_text, allowance = cells[:3]
                match = _PRICE_RE.search(price_text)
                if not name or not match:
                    continue
                category = (
                    "Mobile data reload bundle"
                    if is_reload
                    else "Mobile postpaid data plan"
                )
                unit = "reload bundle" if is_reload else "per month"
                product_name = (
                    f"{name} ({allowance} GB)"
                    if allowance and allowance.lower() != "n/a"
                    else name
                )
                product_id = _slug(f"{table_index}-{name}-{allowance}")
                yield {
                    "product_id": product_id,
                    "product_name": product_name,
                    "category": category,
                    "price": match.group(0).replace(",", ""),
                    "currency": "AUD",
                    "available": True,
                    "unit": unit,
                    "url": f"{response.url}#{product_id}",
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }
