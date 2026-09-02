"""Digicel Nauru promotion tariff tables from Next.js page data."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import scrapy


_PRICE_RE = re.compile(r"(?:AUD\s*)?\$?\s*([0-9]+(?:\.[0-9]{1,2})?)", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _norm_price(price: str) -> str:
    try:
        return str(Decimal(price).normalize())
    except InvalidOperation:
        return price


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        typename = value.get("__typename")
        if typename in {"OfferCard", "JsonTable"}:
            yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


class DigicelNauruPromotionsSpider(scrapy.Spider):
    name = "digicel_nauru_promotions"
    allowed_domains = ["digicelpacific.com", "www.digicelpacific.com"]
    start_urls = [
        "https://www.digicelpacific.com/mobile/nr/promotions/smart-data-sim-plans",
        "https://www.digicelpacific.com/mobile/nr/promotions/new-super-magmein-plans",
    ]
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
        for block in _walk(data):
            if block.get("__typename") == "OfferCard":
                yield from self._parse_offer_card(block, response, scraped_at, seen)
            elif block.get("__typename") == "JsonTable":
                yield from self._parse_json_table(block, response, scraped_at, seen)

    def _parse_offer_card(self, card, response, scraped_at, seen):
        heading = _clean(str(card.get("heading") or ""))
        description = _clean(str(card.get("description") or ""))
        price_text = _clean(str(card.get("price") or ""))
        price_match = _PRICE_RE.search(price_text)
        if not heading or not price_match:
            return

        features = []
        for feature in card.get("features") or []:
            if not isinstance(feature, dict):
                continue
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
        yield from self._emit_item(
            product_name=product_name,
            price_text=price_text,
            category="Mobile prepaid promotion",
            unit=validity or "prepaid bundle",
            features=" | ".join(features) or None,
            response=response,
            scraped_at=scraped_at,
            seen=seen,
        )

    def _parse_json_table(self, table, response, scraped_at, seen):
        for row in table.get("data") or []:
            if not isinstance(row, dict):
                continue
            name = _clean(
                str(
                    row.get("Plan Name")
                    or row.get("Name")
                    or row.get("Plan")
                    or row.get("Offer")
                    or ""
                )
            )
            price_text = _clean(
                str(row.get("Price VIP") or row.get("Price") or row.get("Fee") or "")
            )
            if not name or not price_text:
                continue
            details = [
                f"{key}: {_clean(str(value))}"
                for key, value in row.items()
                if _clean(str(key))
                and key
                not in {
                    "Plan Name",
                    "Name",
                    "Plan",
                    "Offer",
                    "Price VIP",
                    "Price",
                    "Fee",
                }
                and _clean(str(value))
            ]
            validity = _clean(str(row.get("Validity") or "")) or "prepaid bundle"
            yield from self._emit_item(
                product_name=name,
                price_text=price_text,
                category="Mobile prepaid promotion table",
                unit=validity,
                features=" | ".join(details) or None,
                response=response,
                scraped_at=scraped_at,
                seen=seen,
            )

    def _emit_item(
        self,
        product_name: str,
        price_text: str,
        category: str,
        unit: str,
        features: str | None,
        response,
        scraped_at: str,
        seen: set[tuple[str, str]],
    ):
        price_match = _PRICE_RE.search(price_text)
        if not price_match:
            return
        price = price_match.group(1)
        key = (_slug(product_name), _norm_price(price))
        if key in seen:
            return
        seen.add(key)
        product_id = _slug(f"{product_name}-{price}")
        yield {
            "product_id": product_id,
            "product_name": f"Digicel Nauru {product_name}"[:500],
            "category": category,
            "price": price,
            "price_text": price_text,
            "currency": self.currency,
            "available": True,
            "unit": unit,
            "plan_features": features,
            "url": f"{response.url}#{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
