"""Palau PNCC mobile prepaid data plan prices from the public JS bundle."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy


_SCRIPT_RE = re.compile(r'src="([^"]*PrepaidDataPlans[^"]+\.js)"')
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


class PnccPrepaidPwSpider(scrapy.Spider):
    name = "pncc_prepaid_pw"
    allowed_domains = ["pnccpalau.com", "www.pnccpalau.com"]
    start_urls = [
        "https://www.pnccpalau.com/residential-and-personal/mobile/prepaid-data-plans"
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
                "PNCC prepaid bundle script not found on %s", response.url
            )
            return
        yield scrapy.Request(
            response.urljoin(match.group(1)),
            callback=self.parse_bundle,
            meta={"source_url": response.url},
        )

    def parse_bundle(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        source_url = response.meta.get("source_url") or response.url

        data_table = re.search(
            r"const e=\{.*?headers:\[(?P<headers>[^\]]+)\],data:\[(?P<data>.*?)\]\},a=",
            response.text,
        )
        if data_table:
            headers = [
                _clean(value)
                for value in re.findall(r'"([^"]+)"', data_table.group("headers"))
            ]
            rows = [
                _cells(row)
                for row in re.findall(r"\{([^{}]+)\}", data_table.group("data"))
            ]
            if len(rows) >= 2:
                allowances = rows[0]
                validities = rows[1]
                for index, raw_price in enumerate(headers, 1):
                    price_match = _PRICE_RE.search(raw_price)
                    allowance = allowances.get(f"column{index}") or ""
                    validity = validities.get(f"column{index}") or ""
                    if not price_match or not allowance:
                        continue
                    yield self._item(
                        category="Mobile prepaid data plan",
                        name=f"PNCC prepaid data {allowance} {validity}".strip(),
                        price=price_match.group(1),
                        price_text=raw_price,
                        unit=validity,
                        url=source_url,
                        scraped_at=scraped_at,
                    )

        bundle_table = re.search(
            r",a=\{.*?headers:\[(?P<headers>[^\]]+)\],data:\[(?P<data>.*?)\]\};function",
            response.text,
        )
        if bundle_table:
            validities = [
                _clean(value)
                for value in re.findall(r'"([^"]+)"', bundle_table.group("headers"))
            ]
            rows = [
                _cells(row)
                for row in re.findall(r"\{([^{}]+)\}", bundle_table.group("data"))
            ]
            if len(rows) >= 2:
                prices = rows[0]
                data = rows[1]
                texts = rows[2] if len(rows) > 2 else {}
                voice = rows[3] if len(rows) > 3 else {}
                for index, validity in enumerate(validities, 1):
                    raw_price = prices.get(f"column{index}") or ""
                    price_match = _PRICE_RE.search(raw_price)
                    allowance = data.get(f"column{index}") or ""
                    if not price_match or not allowance:
                        continue
                    features = " | ".join(
                        item
                        for item in [
                            allowance,
                            texts.get(f"column{index}") or "",
                            voice.get(f"column{index}") or "",
                        ]
                        if item
                    )
                    yield self._item(
                        category="Mobile prepaid bundle",
                        name=f"PNCC prepaid bundle {allowance} {validity}".strip(),
                        price=price_match.group(1),
                        price_text=raw_price,
                        unit=validity,
                        url=source_url,
                        scraped_at=scraped_at,
                        features=features,
                    )

    def _item(
        self,
        *,
        category: str,
        name: str,
        price: str,
        price_text: str,
        unit: str,
        url: str,
        scraped_at: str,
        features: str | None = None,
    ) -> dict[str, object]:
        product_id = _slug(f"{category}-{name}-{price}")
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "price_text": price_text,
            "currency": self.currency,
            "available": True,
            "unit": unit or "prepaid plan",
            "plan_features": features,
            "url": f"{url}#{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
