"""Tide Table Restaurant and Lounge menu prices in Majuro."""

from __future__ import annotations

from datetime import datetime, timezone
import re

import scrapy


_PRICE_RE = re.compile(r"\$+\s*([0-9]+(?:\s*\.\s*[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

_SECTION_HEADERS = {
    "vodka",
    "gin",
    "bourbon/whiskey",
    "scotch",
    "rum",
    "tequila",
    "beer",
}


def _clean(text: str | None) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _price(value: str) -> str:
    return value.replace(" ", "")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class TideTableMhSpider(scrapy.Spider):
    name = "tide_table_mh"
    allowed_domains = ["rreinc.com", "www.rreinc.com"]
    start_urls = ["http://www.rreinc.com/tidetablemenu.html"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        texts = [_clean(text) for text in response.xpath("//text()").getall()]
        texts = [text for text in texts if text]

        try:
            start = texts.index("COCKTAILS & SPIRITS")
            stop = next(
                index
                for index, text in enumerate(texts[start:], start)
                if text.startswith("All prices listed above")
            )
        except (ValueError, StopIteration):
            self.logger.warning("Could not locate Tide Table priced menu block")
            return

        current_section = "Cocktails and spirits"
        pending_item: str | None = None
        seen: set[str] = set()

        def emit(item_name: str, price: str, unit: str, category: str):
            product_id = _slug(f"{category}-{item_name}-{unit}-{price}")
            if product_id in seen:
                return None
            seen.add(product_id)
            return {
                "product_id": product_id,
                "product_name": f"Tide Table {item_name}",
                "category": category,
                "price": _price(price),
                "price_text": f"${_price(price)}",
                "currency": "USD",
                "available": True,
                "unit": unit,
                "url": f"{response.url}#{product_id}",
                "language": "en",
                "scraped_at_utc": scraped_at,
            }

        for index, text in enumerate(texts[start + 1 : stop], start + 1):
            lower = text.lower()
            if lower in _SECTION_HEADERS:
                current_section = "Beer" if lower == "beer" else text
                pending_item = None
                continue

            tropical = re.match(r"BLENDED TROPICAL DRINKS\s+\$([0-9.]+)", text, re.I)
            if tropical:
                current_section = "Blended tropical drinks"
                for drink in self._tropical_drinks(texts[index + 1 : stop]):
                    item = emit(
                        drink,
                        tropical.group(1),
                        "regular serving",
                        current_section,
                    )
                    if item:
                        yield item
                pending_item = None
                continue

            if text == "Well Drinks (House Brands)":
                pending_item = text
                continue

            if ":" in text and "$" in text:
                item_name, rest = text.split(":", 1)
                price_match = _PRICE_RE.search(rest)
                if not price_match:
                    continue
                item = emit(
                    item_name.strip(),
                    price_match.group(1),
                    "regular serving",
                    current_section,
                )
                if item:
                    yield item
                pending_item = None
                continue

            if "$" in text and pending_item:
                prices = _PRICE_RE.findall(text)
                units = ["happy hour serving", "regular serving"]
                for unit, amount in zip(units, prices):
                    item = emit(pending_item, amount, unit, current_section)
                    if item:
                        yield item
                pending_item = None
                continue

            if current_section == "Beer" and "$" not in text:
                pending_item = text

    def _tropical_drinks(self, texts: list[str]) -> list[str]:
        names = []
        for text in texts:
            if text.lower() == "beer":
                break
            text = text.replace("& many others", "")
            text = text.replace(" and many others", "")
            names.extend(name.strip() for name in re.split(r"\s*,\s*", text))
        return [name for name in names if name]
