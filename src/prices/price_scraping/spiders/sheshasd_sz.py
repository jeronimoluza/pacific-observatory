"""Shesha (Eswatini) -- https://sheshasd.com/product-grids.

Combined liquor store + butchery/meat shop. Plain server-rendered HTML
(no WAF, no impersonation needed -- 200 on bare `requests`). Listing page
/product-grids?page=N carries product name, price and PDP url directly in
the card, so the spider never needs to fetch the PDP.

Card shape (verified 2026-09-11):
    <div class="single-post ...">
      <div class="content">
        <h5><a href="https://sheshasd.com/product-detail/du-toitskloof">DU TOITSKLOOF</a></h5>
        <p class="price"><del class="text-muted">E154.00</del> E154.00 </p>
      </div>
    </div>

Enumerability MEASURED 2026-09-11: page=1..8 walked, 21 cards/page (last
page 15, page 9 empty/3 pinned-only), 69 distinct product-detail slugs
total. Three slugs (du-toitskloof, kwv-brand-and-cola,
ballantines-gift-pack) reappear on every page -- a pinned/featured block,
not a pagination bug (confirmed: pages 2-7 each contribute 9 genuinely NEW
slugs beyond those three). Stop condition: page whose card set contains
zero NEW slugs.

Catalog mix: South African wine/spirits/beer brands (Du Toitskloof, KWV,
Ballantine's, Hennessy, Jameson, Glenfiddich, Jack Daniels, Bell's, Amstel,
Savanna Dry, Russian Bear, Red Heart rum) plus raw meat cuts (beef chuck/
t-bone/stew, pork chops/slices/sausage, chicken slices) and a couple of
prepared meal-for-N items (umgcwembe). Wide mix of COICOP 01 (meat) and
02.1 (alcohol) -- coicop_codes left unset for the classifier.

Currency: "E" prefix = Emalangeni (SZL), matching countries.yaml default
for Eswatini. Price cell sometimes shows a struck-through <del> "was"
price followed by the current price -- the spider takes the LAST number in
the cell (the current/discounted price), matching the on-page display.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_CARD_RE_A = re.compile(
    r'<h5><a href="(https://sheshasd\.com/product-detail/[^"]+)">([^<]+)</a></h5>'
    r'.*?<p class="price">(.*?)</p>',
    re.S,
)
_CARD_RE_B = re.compile(
    r'<h3><a href="(https://sheshasd\.com/product-detail/[^"]+)">([^<]+)</a></h3>'
    r"\s*<span>([^<]+)</span>",
    re.S,
)
_PRICE_RE = re.compile(r"E\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", re.I)


class SheshasdSzSpider(scrapy.Spider):
    name = "sheshasd_sz"
    allowed_domains = ["sheshasd.com"]
    currency = "SZL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    MAX_PAGES = 60

    async def start(self):
        self._seen: set[str] = set()
        yield scrapy.Request(
            "https://sheshasd.com/product-grids?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = _CARD_RE_A.findall(response.text) + _CARD_RE_B.findall(response.text)
        new_count = 0
        for url, name, price_html in cards:
            m = _PRICE_RE.findall(price_html)
            if not m:
                continue
            price = m[-1].replace(",", "")
            name = name.strip()
            if not name or url in self._seen:
                continue
            self._seen.add(url)
            new_count += 1
            yield {
                "product_id": url.rsplit("/", 1)[-1],
                "product_name": name,
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if new_count > 0 and page < self.MAX_PAGES:
            yield scrapy.Request(
                f"https://sheshasd.com/product-grids?page={page + 1}",
                callback=self.parse_page,
                meta={"page": page + 1},
            )
