"""Ocean Basket Botswana server-rendered menu extractor."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy


PRICE_RE = re.compile(r"P\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b", re.I)
SEEDS = (
    ("https://botswana.oceanbasket.com/menu/main/", "main"),
)


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


class BotswanaOceanbasketMenuSpider(scrapy.Spider):
    name = "botswana_oceanbasket_menu"
    allowed_domains = ["botswana.oceanbasket.com"]
    custom_settings = {"DOWNLOAD_DELAY": 0.5, "CONCURRENT_REQUESTS_PER_DOMAIN": 1}

    async def start(self):
        for url, menu in SEEDS:
            yield scrapy.Request(url, callback=self.parse, cb_kwargs={"menu": menu})

    def parse(self, response, menu: str):
        seen: set[tuple[str, str, str]] = set()
        for card in response.css("span.menu_item"):
            name = clean(card.css("h4::text").get())
            price_text = clean(card.css("span.price::text").get())
            if not name or not price_text:
                continue
            category = clean(card.xpath(
                "ancestor::div[contains(concat(' ', normalize-space(@class), ' '), "
                "' menu_item_wrap ')][1]//div[contains(@class, 'menu_title')]//text()[normalize-space()][1]"
            ).get())
            for ordinal, raw_price in enumerate(PRICE_RE.findall(price_text), start=1):
                price = raw_price.replace(",", "")
                key = (name.lower(), price, menu)
                if key in seen:
                    continue
                seen.add(key)
                product_id = f"oceanbasket:{menu}:{name.lower()}:{ordinal}"
                yield {
                    "product_id": product_id,
                    "product_name": name,
                    "price": price,
                    "currency": "BWP",
                    "country": "Botswana",
                    "sector": "food_and_beverages",
                    "available": True,
                    "category": category or None,
                    "url": f"{response.url}#item={quote(product_id, safe='')}",
                    "language": "en",
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
