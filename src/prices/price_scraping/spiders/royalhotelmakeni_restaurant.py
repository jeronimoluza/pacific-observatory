"""Royal Hotel Makeni restaurant menu parser."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy


_RESTAURANT_URL = "https://royalhotelmakenisl.com/the-restaurant/"
_PRICE_RE = re.compile(r"(?:^|\s)(?:le|sle)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?=\s|$)", re.I)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _amount(value: str) -> str | None:
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None
    return f"{number:.2f}" if number > 0 else None


class RoyalhotelmakeniRestaurantSpider(scrapy.Spider):
    name = "royalhotelmakeni_restaurant"
    allowed_domains = ["royalhotelmakenisl.com", "www.royalhotelmakenisl.com"]
    currency = "SLE"
    language = "en"
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request(_RESTAURANT_URL, callback=self.parse_menu)

    def parse_menu(self, response):
        seen: set[tuple[str, str]] = set()
        # The page has one dedicated food-menu item per atomic name/price row.
        blocks = response.css(".cs-food-menu-item")
        for block in blocks:
            name = _clean(" ".join(block.css(".cs-food-menu-title .title-wrap::text").getall()))
            price_text = _clean(" ".join(block.css(".cs-food-menu-price::text").getall()))
            match = _PRICE_RE.search(price_text)
            if not match:
                continue
            price = _amount(match.group(1))
            if not (name and price) or name.casefold() in {"our menus", "menu"}:
                continue
            key = (name.casefold(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = f"{name.casefold()}-{price}".replace(" ", "-")
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": f"{response.url.split('?', 1)[0]}#item={quote(product_id, safe='')}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
