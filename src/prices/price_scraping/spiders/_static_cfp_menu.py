"""Helpers for static French Pacific menu pages with CFP/XPF prices."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(
    r"(?P<prefix>(?:\d+\s*cl|verre|bouteille|personne|pers)\s*:?\s*)?"
    r"(?P<amount>\d+(?:[\s\u00a0\u202f.]\d{3})*(?:,\d{1,2})?)\s*"
    r"(?P<currency>F\s*CFP|FCFP|CFP|XPF|F)\b",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SKIP_NAME_RE = re.compile(
    r"^(menu|menus|carte|reserve|reservez|image|coup de coeur|allergens?|"
    r"liste|horaires?|schedules?|contact|accueil|plats?|entrees?|desserts?|"
    r"boissons?|vins?|side|child|children|prix|tarif|\*+)$",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


def _normalize_price(raw: str) -> str | None:
    value = raw.replace("\xa0", " ").replace("\u202f", " ")
    value = re.sub(r"\s+", "", value)
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(".", "")
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed < 100:
        return None
    return str(int(parsed)) if parsed.is_integer() else f"{parsed:.2f}"


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")[:160]


class StaticCfpMenuSpider(scrapy.Spider):
    """Extracts product-like menu rows where nearby text names a CFP price."""

    name = None
    venue_name = ""
    currency = "XPF"
    language = "fr"
    price_before_name = False
    max_name_distance = 7

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        texts = [
            _clean(text)
            for text in response.xpath(
                "//body//text()[not(ancestor::script) and not(ancestor::style)]"
            ).getall()
        ]
        texts = [text for text in texts if text]
        seen: set[tuple[str, str]] = set()

        for index, text in enumerate(texts):
            for match in _PRICE_RE.finditer(text):
                price = _normalize_price(match.group("amount"))
                if price is None:
                    continue
                name = self._nearby_name(texts, index)
                if not name:
                    continue
                prefix = _clean(match.group("prefix"))
                unit = prefix.rstrip(":") if prefix else "menu item"
                key = (name.lower(), price)
                if key in seen:
                    continue
                seen.add(key)

                product_id = _slug(f"{self.name}-{name}-{price}-{len(seen)}")
                yield {
                    "product_id": product_id,
                    "product_name": f"{self.venue_name} {name}"[:500],
                    "category": "Restaurant menu item",
                    "price": price,
                    "price_text": match.group(0),
                    "currency": self.currency,
                    "available": True,
                    "unit": unit,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

    def _nearby_name(self, texts: list[str], price_index: int) -> str | None:
        if self.price_before_name:
            span = range(
                price_index + 1,
                min(len(texts), price_index + self.max_name_distance + 1),
            )
        else:
            span = range(
                price_index - 1,
                max(-1, price_index - self.max_name_distance - 1),
                -1,
            )
        for candidate_index in span:
            candidate = self._candidate_name(texts[candidate_index])
            if candidate:
                return candidate
        return None

    @staticmethod
    def _candidate_name(text: str) -> str | None:
        text = _PRICE_RE.sub("", _clean(text)).strip(" -:;")
        if not text or len(text) > 120:
            return None
        if _SKIP_NAME_RE.search(text):
            return None
        if re.fullmatch(r"[\d\s:.,/+-]+", text):
            return None
        return text
