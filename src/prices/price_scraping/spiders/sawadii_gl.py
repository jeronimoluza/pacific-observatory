"""Sawadii Take-away's server-rendered Nuuk online menu (DKK)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha1

import scrapy

_MENU = "https://www.sawadii.gl/en/menu"
_PRICE = re.compile(r"^(?P<from>From\s+)?(?P<price>[0-9]+(?:\.[0-9]{1,2})?)\s*DKK$", re.I)
_BARE_NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]{1,2})?$")


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


class SawadiiGlSpider(scrapy.Spider):
    name = "sawadii_gl"
    allowed_domains = ["www.sawadii.gl", "sawadii.gl"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request(_MENU, callback=self.parse_menu)

    def parse_menu(self, response):
        # Text order is stable: item name, optional bare numeric mirror, then
        # the currency-labelled amount. Use only the labelled amount as price.
        lines = [_clean(v) for v in response.css("body *::text").getall()]
        lines = [v for v in lines if v]
        seen: set[tuple[str, str, bool]] = set()
        for index, line in enumerate(lines):
            match = _PRICE.fullmatch(line)
            if not match:
                continue
            prior = index - 1
            if prior >= 0 and _BARE_NUMBER.fullmatch(lines[prior]):
                prior -= 1
            if prior >= 0 and lines[prior].casefold() == "from":
                prior -= 1
            if prior < 0:
                continue
            name = lines[prior]
            if len(name) < 3 or _PRICE.fullmatch(name) or _BARE_NUMBER.fullmatch(name):
                continue
            is_from = bool(match["from"])
            key = (name.casefold(), match["price"], is_from)
            if key in seen:
                continue
            seen.add(key)
            item_id = sha1("|".join(map(str, key)).encode()).hexdigest()[:16]
            yield {
                "product_id": item_id, "product_name": name[:500],
                "price": match["price"], "currency": "DKK", "unit": "menu_item",
                "from_price": is_from, "price_kind": "from" if is_from else "fixed",
                "available": True, "locality": "Nuuk, Greenland", "category": None,
                "url": f"{response.url.split('?', 1)[0]}#{item_id}", "language": "da",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
