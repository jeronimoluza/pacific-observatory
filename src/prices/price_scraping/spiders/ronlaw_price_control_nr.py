"""Nauru RONLAW price-control fuel order."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

import scrapy


_API_URL = "https://ronlaw.gov.nr/api/pdf/search"
_PDFVIEWER_URL = (
    "https://ronlaw.gov.nr/pdfviewer/docs%252Flaws%252F2026%252F"
    "Price%2520Control%2520Order%2520No%25202%25202026_serv5.pdf"
)
_TARGET_TITLE = "Price Control Order No 2 2026_serv5.pdf"
_PRICE_RE = re.compile(
    r"Maximum (?P<tier>wholesale|retail) price at which "
    r"(?P<fuel>diesel|petrol|Jet ?A1) may be sold as "
    r"\$(?P<price>[0-9]+(?:\.[0-9]+)?)/litre",
    re.I,
)


def _clean(text: object) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split())


class RonlawPriceControlNrSpider(scrapy.Spider):
    name = "ronlaw_price_control_nr"
    allowed_domains = ["ronlaw.gov.nr"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        body = {
            "query": {
                "query_string": {
                    "query": '"Price Control Order No.2" AND 2026',
                }
            },
            "size": 10,
            "_source": ["title", "year", "file_path", "pages.page_content"],
        }
        yield scrapy.Request(
            _API_URL,
            method="POST",
            body=json.dumps(body),
            headers={"Content-Type": "application/json"},
            callback=self.parse,
        )

    def parse(self, response):
        payload = json.loads(response.text)
        hits = payload.get("hits", {}).get("hits", [])
        source = None
        for hit in hits:
            candidate = hit.get("_source") or {}
            if candidate.get("title") == _TARGET_TITLE:
                source = candidate
                break
        if source is None:
            self.logger.warning("RONLAW target price-control order not found")
            return

        text = _clean(
            " ".join(
                page.get("page_content", "")
                for page in source.get("pages", [])
                if isinstance(page, dict)
            )
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        for match in _PRICE_RE.finditer(text):
            tier = match.group("tier").lower()
            fuel = match.group("fuel").replace(" ", "")
            price = match.group("price")
            row_key = f"{_TARGET_TITLE}|{tier}|{fuel}|{price}"
            product_id = hashlib.sha1(row_key.encode("utf-8")).hexdigest()[:16]
            yield {
                "product_id": product_id,
                "product_name": f"Nauru maximum {tier} fuel price - {fuel}",
                "category": "Fuel price control",
                "price": price,
                "currency": self.currency,
                "available": True,
                "unit": "litre",
                "effective_date": "2026-05-29",
                "url": f"{_PDFVIEWER_URL}#price-{product_id}",
                "source_api_url": response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
