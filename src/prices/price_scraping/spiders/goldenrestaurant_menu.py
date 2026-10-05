"""The Golden Restaurant menu (Freetown, Sierra Leone)."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"\bL(?:E|e)\s*(?P<amount>\d+(?:[.,]\d{1,2})?)\b")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_START_RE = re.compile(r"^delicious menu/dishes$", re.I)
_END_RE = re.compile(r"^open daily from\b", re.I)
_SKIP_EXACT = {
    "special selection",
    "view all menu",
    "view menu",
}
_SKIP_PREFIXES = (
    "call ",
    "book ",
    "email ",
    "whatsapp ",
)


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(text.replace("\xa0", " ").split()).strip()


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value.lower()).strip("-")[:160]


def _price(value: str) -> str | None:
    try:
        parsed = float(value.replace(",", "."))
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return str(int(parsed)) if parsed.is_integer() else f"{parsed:.2f}"


class GoldenrestaurantMenuSpider(scrapy.Spider):
    name = "goldenrestaurant_menu"
    allowed_domains = ["thegoldenrestaurant.netlify.app"]
    start_urls = ["https://thegoldenrestaurant.netlify.app/"]
    currency = "SLL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
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
        menu_texts = self._menu_slice([text for text in texts if text])
        seen: set[tuple[str, str]] = set()

        for index, text in enumerate(menu_texts):
            match = _PRICE_RE.search(text)
            if not match:
                continue
            price = _price(match.group("amount"))
            if price is None:
                continue
            name = self._nearby_name(menu_texts, index, text[: match.start()])
            if not name:
                continue
            description = self._description(menu_texts, index)
            key = (name.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = hashlib.sha1(f"{name}|{price}".encode("utf-8")).hexdigest()[:16]
            row = {
                "product_id": product_id,
                "product_name": f"The Golden Restaurant {name}"[:500],
                "category": "Restaurant menu item",
                "price": price,
                "price_text": match.group(0),
                "currency": self.currency,
                "available": True,
                "unit": "menu item",
                "vendor": "The Golden Restaurant",
                "url": f"{response.url}#menu-{_slug(name)}-{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            if description:
                row["description"] = description[:500]
            yield row

    @staticmethod
    def _menu_slice(texts: list[str]) -> list[str]:
        start = next((i for i, text in enumerate(texts) if _START_RE.match(text)), 0)
        end = next(
            (i for i, text in enumerate(texts[start:], start) if _END_RE.match(text)),
            len(texts),
        )
        return texts[start:end]

    def _nearby_name(self, texts: list[str], price_index: int, inline_label: str) -> str | None:
        inline_label = _clean(inline_label).strip(" -:;,")
        inline_label = re.sub(r"^(quick lunch|special)\b", "", inline_label, flags=re.I).strip(" -:")
        if self._candidate_name(inline_label):
            return inline_label
        for candidate_index in range(price_index - 1, max(-1, price_index - 5), -1):
            candidate = self._candidate_name(texts[candidate_index])
            if candidate:
                return candidate
        return None

    @staticmethod
    def _candidate_name(text: str) -> str | None:
        candidate = _PRICE_RE.sub("", _clean(text)).strip(" -:;,")
        lowered = candidate.lower()
        if not candidate or lowered in _SKIP_EXACT:
            return None
        if any(lowered.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return None
        if len(candidate) > 90 or re.fullmatch(r"[\d\s:.,/+-]+", candidate):
            return None
        if not re.search(r"[A-Za-z]", candidate):
            return None
        return candidate

    @staticmethod
    def _description(texts: list[str], price_index: int) -> str | None:
        if price_index + 1 >= len(texts):
            return None
        candidate = _PRICE_RE.sub("", _clean(texts[price_index + 1])).strip(" -:;,")
        if not candidate or len(candidate) > 160:
            return None
        if re.fullmatch(r"[\d\s:.,/+-]+", candidate):
            return None
        if _END_RE.match(candidate) or _START_RE.match(candidate):
            return None
        return candidate
