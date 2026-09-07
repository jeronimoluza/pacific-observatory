"""Palm Sugar Cafeteria Honiara menu prices."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"(?P<label>[^$]{0,40}?)\$\s*(?P<amount>\d+(?:\.\d{1,2})?)")
_AMOUNT_RE = re.compile(r"^\d+(?:\.\d{1,2})?$")
_SECTION_NAMES = {
    "BREAKFAST",
    "Coffee/Smoothies/Milkshake",
    "ALL DAY LUNCH",
    "Sandwiches/Wraps/Hotdog",
    "All DAY KIDS Meal",
    "FRESH SALAD",
    "BIG BURGERS",
    "TASTE of ASIA",
    "Something Light",
    "PIZZA",
}
_SKIP_PREFIXES = (
    "choice of",
    "with ",
    "including ",
    "and ",
    "standard",
    "thick",
    "medium",
    "large",
    "small",
)
_SKIP_EXACT = {
    "$",
    "beef",
    "chicken",
    "fish",
    "our menu",
    "pork",
    "port",
    "services",
    "tuna",
    "trading hours",
    "reservation",
    "our chef and his team has compiled a mouth-watering menu that is capable to satisfy everyone.",
}


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(text.replace("\xa0", " ").split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:180]


def _price(value: str) -> str | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return str(int(parsed)) if parsed.is_integer() else f"{parsed:.2f}"


class PalmSugarSbSpider(scrapy.Spider):
    name = "palmsugar_sb"
    allowed_domains = ["palmsugar.com.sb", "www.palmsugar.com.sb"]
    start_urls = ["https://palmsugar.com.sb/"]
    currency = "SBD"
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
        texts = [text for text in texts if text]
        texts = self._menu_slice(texts)
        seen: set[tuple[str, str]] = set()

        for index, text in enumerate(texts):
            if text in _SECTION_NAMES:
                continue
            pairs = []
            if text == "$" and index + 1 < len(texts) and _AMOUNT_RE.match(texts[index + 1]):
                pairs.append(("", texts[index + 1]))
            elif index and texts[index - 1] == "$" and _AMOUNT_RE.match(text):
                continue
            else:
                pairs.extend((m.group("label"), m.group("amount")) for m in _PRICE_RE.finditer(text))

            for raw_label, amount in pairs:
                price = _price(amount)
                if price is None:
                    continue
                name = self._nearby_name(texts, index, raw_label)
                if not name:
                    continue
                key = (name.lower(), price)
                if key in seen:
                    continue
                seen.add(key)
                product_id = hashlib.sha1(f"{name}|{price}".encode("utf-8")).hexdigest()[:16]
                yield {
                    "product_id": product_id,
                    "product_name": name[:500],
                    "category": "Prepared-food menu",
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    "url": f"{response.url}#menu-{_slug(name)}-{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

    @staticmethod
    def _menu_slice(texts: list[str]) -> list[str]:
        start = next((i for i, text in enumerate(texts) if text.lower() == "our menu"), 0)
        end = next(
            (i for i, text in enumerate(texts[start:], start) if text.lower() == "services"),
            len(texts),
        )
        return texts[start:end]

    def _nearby_name(self, texts: list[str], price_index: int, raw_label: str) -> str | None:
        label = _clean(raw_label).strip(" -:")
        label_is_variant = (
            not label
            or label.lower().startswith(_SKIP_PREFIXES)
            or re.fullmatch(r'\d+"\s*', label)
        )
        base = self._find_base_name(texts, price_index)
        if not base:
            return None
        if label and label_is_variant:
            return f"{base} ({label})"
        if label and not label_is_variant and len(label) > len(base):
            return label
        return base

    def _find_base_name(self, texts: list[str], price_index: int) -> str | None:
        for candidate_index in range(price_index - 1, max(-1, price_index - 8), -1):
            candidate = self._candidate_name(texts[candidate_index])
            if candidate:
                return candidate
        return None

    @staticmethod
    def _candidate_name(text: str) -> str | None:
        if _clean(text).startswith("$"):
            return None
        candidate = _PRICE_RE.sub("", _clean(text)).strip(" -:;,")
        lowered = candidate.lower()
        if not candidate or lowered in _SKIP_EXACT:
            return None
        if candidate in _SECTION_NAMES or lowered.startswith(_SKIP_PREFIXES):
            return None
        if _AMOUNT_RE.match(candidate) or len(candidate) > 90:
            return None
        if "," in candidate and len(candidate) > 28:
            return None
        return candidate
