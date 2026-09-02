"""Palau PNCC postpaid mobile plan prices from the public JS bundle."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy


_SCRIPT_RE = re.compile(r'src="([^"]*PostpaidPlans[^"]+\.js)"')
_PRICE_RE = re.compile(r"\$?\s*([0-9]+(?:\.[0-9]{1,2})?)")
_CELL_RE = re.compile(r"(column\d+):(?:'([^']*)'|\"([^\"]*)\")")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _cells(row_blob: str) -> dict[str, str]:
    return {
        key: _clean(single or double)
        for key, single, double in _CELL_RE.findall(row_blob)
    }


def _feature(label: str, value: str | None) -> str | None:
    value = _clean(value)
    if not value or value.lower().startswith("none"):
        return None
    return f"{label}: {value}"


class PnccPostpaidPwSpider(scrapy.Spider):
    name = "pncc_postpaid_pw"
    allowed_domains = ["pnccpalau.com", "www.pnccpalau.com"]
    start_urls = [
        "https://www.pnccpalau.com/residential-and-personal/mobile/postpaid-plans"
    ]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        match = _SCRIPT_RE.search(response.text)
        if not match:
            self.logger.warning(
                "PNCC postpaid bundle script not found on %s", response.url
            )
            return
        yield scrapy.Request(
            response.urljoin(match.group(1)),
            callback=self.parse_bundle,
            meta={"source_url": response.url},
        )

    def parse_bundle(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        source_url = response.meta.get("source_url") or self.start_urls[0]

        data_match = re.search(r"const\s+\w+=\[(?P<data>.*?)\];function", response.text)
        if not data_match:
            self.logger.warning(
                "PNCC postpaid data array not found in %s", response.url
            )
            return

        for row in (
            _cells(blob)
            for blob in re.findall(r"\{([^{}]+)\}", data_match.group("data"))
        ):
            plan = row.get("column1") or ""
            price_text = row.get("column2") or ""
            price_match = _PRICE_RE.search(price_text)
            if not plan or not price_match:
                continue
            features = " | ".join(
                value
                for value in [
                    _feature("airtime minutes", row.get("column3")),
                    _feature("additional airtime", row.get("column4")),
                    _feature("local text send/receive", row.get("column5")),
                    _feature("mobile data included", row.get("column6")),
                ]
                if value
            )
            product_id = _slug(f"{plan}-{price_match.group(1)}")
            yield {
                "product_id": product_id,
                "product_name": f"PNCC postpaid {plan}"[:500],
                "category": "Mobile postpaid plan",
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": "per month",
                "plan_features": features or None,
                "url": f"{source_url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
