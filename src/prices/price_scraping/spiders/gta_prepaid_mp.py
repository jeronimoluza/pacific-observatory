"""GTA Guam/CNMI prepaid mobile plan and data add-on prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class GtaPrepaidMpSpider(scrapy.Spider):
    name = "gta_prepaid_mp"
    allowed_domains = ["gta.net", "www.gta.net"]
    start_urls = ["https://www.gta.net/mobile/prepaid/"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for card in response.css(".plan-block"):
            title_text = _clean(" ".join(card.css(".plan-title ::text").getall()))
            price_match = _PRICE_RE.search(title_text)
            if not price_match:
                continue
            duration = _clean(" ".join(card.css(".plan-title .unit::text").getall()))
            details = []
            for detail in card.css(".plan-details li"):
                label = _clean(" ".join(detail.css(".lbl ::text, .lbl::text").getall()))
                value = _clean(
                    " ".join(detail.css(".details ::text, .details::text").getall())
                )
                if label and value:
                    details.append(f"{label}: {value}")
            features = " | ".join(details)
            prefix = "GTA prepaid plan"
            if "Local Data" in features:
                prefix = "GTA SIM kit prepaid plan"
            product_id = _slug(f"plan-{title_text}-{features}")
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": f"{prefix} {duration}".strip(),
                "category": "Mobile prepaid plan",
                "price": price_match.group(1),
                "price_text": title_text,
                "currency": self.currency,
                "available": True,
                "unit": duration or "prepaid plan",
                "plan_features": features or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for table in response.css("table"):
            headers = [
                _clean(" ".join(header.css("::text").getall()))
                for header in table.css("th")
            ]
            if headers[:2] != ["Data", "Cost"]:
                continue
            for row in table.css("tr")[1:]:
                cells = [
                    _clean(" ".join(cell.css("::text").getall()))
                    for cell in row.css("td")
                ]
                if len(cells) < 2:
                    continue
                allowance, price_text = cells[0], cells[1]
                price_match = _PRICE_RE.search(price_text)
                if not allowance or not price_match:
                    continue
                product_id = _slug(f"data-{allowance}-{price_text}")
                if product_id in seen:
                    continue
                seen.add(product_id)
                yield {
                    "product_id": product_id,
                    "product_name": f"GTA prepaid data add-on {allowance}",
                    "category": "Mobile prepaid data add-on",
                    "price": price_match.group(1),
                    "price_text": price_text,
                    "currency": self.currency,
                    "available": True,
                    "unit": allowance,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
