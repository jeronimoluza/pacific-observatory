"""Sinkor Palace / Silver Spoon Restaurant (Monrovia, Liberia) --
https://www.sinkorpalace.com/restaurantmenu

Hotel restaurant menu: Liberian dishes, salads, handhelds, pasta, pizza,
mains, sides, chef specials, plus drinks. COICOP 11.1 catering -- a division
retailer SKU catalogs structurally cannot reach.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124: a Wix site whose
restaurant-menu widget is SERVER-RENDERED into the page (1.4 MB of HTML, ~100
priced items in the raw response), so this is Tier 1A and no Playwright is
needed even though the shell is a Wix SPA. Item markup is Wix's stable
data-hook contract:

    <div data-hook="item.container">
      <p data-hook="item.name">Sweet Potatoes</p>
      <p data-hook="item.description">Lightly fried sweet potato wedges.</p>
      <div data-hook="item.price-container">
        <p data-hook="item.price">$6</p>

TRAP recorded: the widget's CATEGORY TAB labels also contain dollar amounts
(e.g. a tab literally reads "Liberian Dishes - $8"). A page-level price regex
picks those up as if they were items. This spider only reads
data-hook="item.price" inside an item container, so tab labels can never
become rows.

CURRENCY: USD. Bare "$" with no machine-readable code; Liberia is
dual-currency and Monrovia hotel restaurants quote US dollars -- judgement
call, recorded not assumed, and consistent with the sibling amseaview_menu
source which states it in words.

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

_URL = "https://www.sinkorpalace.com/restaurantmenu"
_PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")


class SinkorPalaceMenuSpider(scrapy.Spider):
    name = "sinkor_palace_menu"
    allowed_domains = ["sinkorpalace.com", "www.sinkorpalace.com"]
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
        items = response.css('[data-hook="item.container"]')
        self.logger.info(f"{self.name}: {len(items)} menu item containers")
        for item in items:
            name = item.css('[data-hook="item.name"]::text').get()
            price_text = item.css('[data-hook="item.price"]::text').get()
            if not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price = m.group(1).replace(",", "")
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
