"""Digicel Nauru prepaid bundle prices from Next.js page data."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

import scrapy


_PRICE_RE = re.compile(r"(?:AUD\s*)?\$?\s*([0-9]+(?:\.[0-9]{1,2})?)", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("__typename") == "OfferCard":
            yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


class DigicelNauruBundlesSpider(scrapy.Spider):
    name = "digicel_nauru_bundles"
    allowed_domains = ["digicelpacific.com", "www.digicelpacific.com"]
    start_urls = ["https://www.digicelpacific.com/mobile/nr/bundles"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        script = response.css("script#__NEXT_DATA__::text").get()
        if not script:
            self.logger.warning("No __NEXT_DATA__ payload found on %s", response.url)
            return

        try:
            data = json.loads(script)
        except json.JSONDecodeError as exc:
            self.logger.warning("Could not decode Digicel Nauru JSON: %s", exc)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for index, card in enumerate(_walk(data), 1):
            heading = _clean(str(card.get("heading") or ""))
            description = _clean(str(card.get("description") or ""))
            price_text = _clean(str(card.get("price") or ""))
            price_match = _PRICE_RE.search(price_text)
            if not heading or not price_match:
                continue

            features = []
            for feature in card.get("features") or []:
                highlight = _clean(str(feature.get("highlight") or ""))
                detail = _clean(str(feature.get("detail") or ""))
                if highlight and detail:
                    features.append(f"{highlight} {detail}")
                elif highlight or detail:
                    features.append(highlight or detail)
            validity = next(
                (
                    item.replace("Validity", "").strip()
                    for item in features
                    if "validity" in item.lower()
                ),
                None,
            )
            product_name = " ".join(part for part in [description, heading] if part)
            key = (product_name.lower(), price_match.group(1), validity or "")
            if key in seen:
                continue
            seen.add(key)
            product_id = _slug(f"{index}-{product_name}-{price_match.group(1)}")

            yield {
                "product_id": product_id,
                "product_name": product_name[:500],
                "category": "Mobile prepaid bundle",
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": validity or "prepaid bundle",
                "plan_features": " | ".join(features) or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
