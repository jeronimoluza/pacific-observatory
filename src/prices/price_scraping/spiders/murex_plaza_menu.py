"""Murex Plaza Hotel restaurant menu -- https://menu.murexplaza.com/

Monrovia hotel restaurant. Prepared-food and beverage prices (COICOP 11.1
catering), a division that retailer SKU sources structurally cannot reach.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124: a small
Laravel/Apache menu app, fully server-rendered on one page, ~14 priced items
visible in the raw HTML with no JS required. Card markup:

    <div class="product">
      <div class="product-desc">
        <h4><a ...>Vegetable Fried Noodles</a></h4>
        <p>Mixed vegetable, onion, garlic, Ginger &amp; noodles</p>
        <p class="product-price">$12</p>

There is no sitemap and no pagination -- the whole menu is the one page, so
"enumerability" here means the single document is the complete catalog rather
than a curated carousel. A menu is a legitimate small catalog; the >=5-row
gate is the thing that actually has to pass.

CURRENCY: USD. Prices render as bare "$" with no machine-readable code, and
Liberia is dual-currency -- but Monrovia hotel restaurants quote US dollars
and the sibling amseaview_menu source states "Prices are in US dollars" in so
many words. Judgement call, recorded not assumed.

Page family parsed: listing (the single menu page).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


def _anchor(url: str, name: str) -> str:
    """Give every row on a one-page menu its own URL.

    The repo's DuplicationPipeline drops any item whose `url` it has already
    seen this run (md5 of the url string), so a menu where every dish shares
    the page URL collapses to ONE row -- measured here on 2026-09-12:
    item_scraped_count went to 1 with 14 dishes parsed. Appending a slug of the
    dish name as a fragment is both honest (it is an anchor into that page) and
    the right identity for a menu, where the dish name IS the product key.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{url}#{slug}" if slug else url

_URL = "https://menu.murexplaza.com/"


class MurexPlazaMenuSpider(scrapy.Spider):
    name = "murex_plaza_menu"
    allowed_domains = ["menu.murexplaza.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_menu)

    def parse_menu(self, response):
        cards = response.css("div.product")
        self.logger.info(f"{self.name}: {len(cards)} menu cards")
        for card in cards:
            name = card.css("div.product-desc h4 a::text").get()
            if not name:
                name = card.css("div.product-desc h4::text").get()
            price = card.css("p.product-price::text").get()
            if not name or not price:
                continue
            price = price.strip().lstrip("$").replace(",", "").strip()
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            yield {
                "product_id": None,
                "product_name": name.strip()[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": _anchor(response.url, name.strip()),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
