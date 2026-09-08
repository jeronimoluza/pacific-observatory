"""
Spider for Himawari Store & Restaurant (Saipan, Northern Mariana Islands) —
himawarisaipan.com.

A Japanese restaurant + bakery/store built on the "fbgcdn.com" website
builder (small local-business restaurant sites, no anti-bot). The single
GET https://www.himawarisaipan.com/menu carries ONE
<script type="application/ld+json"> block whose top-level object is a
schema.org Restaurant. Its `menu` field is itself a JSON **string** (not a
nested object) that needs a second json.loads — that string decodes to a
Menu object with `hasMenuSection[]` -> `hasMenuItem[]`, each item an
Offer{price, priceCurrency}. Confirmed live 2026-09-06: 211 MenuItem
entries parse out via a recursive @type=="MenuItem" walk, price in USD
(Gibraltar's currenciesAccepted / Saipan uses USD like the rest of the
CNMI).

Every item is a restaurant meal/bakery good — narrow single-COICOP
(11.1.1.2) source, channel=other (dining, same convention as hotpepper_jp).
No pagination: one page carries the whole menu (211 items observed).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_MENU_URL = "https://www.himawarisaipan.com/menu"


def _find_menu_items(node):
    """Recursively walk a parsed JSON-LD tree and yield every MenuItem dict."""
    if isinstance(node, dict):
        if node.get("@type") == "MenuItem":
            yield node
        for value in node.values():
            yield from _find_menu_items(value)
    elif isinstance(node, list):
        for value in node:
            yield from _find_menu_items(value)


class HimawarisaipanMpSpider(scrapy.Spider):
    name = "himawarisaipan_mp"
    allowed_domains = ["himawarisaipan.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_MENU_URL, callback=self.parse_menu, errback=self.errback)

    def parse_menu(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        blocks = response.css('script[type="application/ld+json"]::text').getall()
        found = 0
        for block in blocks:
            try:
                doc = json.loads(block)
            except json.JSONDecodeError:
                continue
            # `menu` is a JSON-encoded string nested inside the Restaurant
            # object — decode it a second time before walking for items.
            menu_raw = doc.get("menu") if isinstance(doc, dict) else None
            if isinstance(menu_raw, str):
                try:
                    menu_doc = json.loads(menu_raw)
                except json.JSONDecodeError:
                    menu_doc = None
            else:
                menu_doc = menu_raw

            for item in _find_menu_items(menu_doc if menu_doc is not None else doc):
                name = item.get("name")
                offer = item.get("offers") or {}
                price = offer.get("price")
                currency = offer.get("priceCurrency") or self.currency
                if not name or price is None:
                    continue
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue
                found += 1
                yield {
                    "product_id": None,
                    "product_name": name,
                    "price": price,
                    "currency": currency,
                    "category": None,
                    # All 211 items share one physical page. DuplicationPipeline
                    # dedups on item["url"], so a bare shared URL would keep
                    # only the first item and silently drop the rest — append
                    # a per-item fragment to make each url unique.
                    "url": f"{_MENU_URL}#item-{found}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
        logger.info(f"{self.name}: extracted {found} menu items")

    def errback(self, failure):
        logger.error("himawarisaipan_mp: request failed %s — %r", failure.request.url, failure.value)
