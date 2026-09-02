"""
Metro Markets (Egypt) -- https://www.metro-markets.com/. Real, live
supermarket chain (distinct from the pre-existing `metro_pk` Pakistan
source), Laravel-based storefront, fully server-rendered -- Tier 1A, no
Playwright needed (confirmed live 2026-09-01: `curl_cffi` alone returns
full product cards with names and prices in raw HTML; a Playwright render
of the same page showed no additional XHR/API call, confirming the catalog
is genuinely SSR, not client-fetched).

The homepage exposes only 6 featured top-level categories --
Bakery(9), Confectionary(20), Dairy(6), Metro(39), Paper-Products(25),
Yameesh(41) -- via `/categoryl1/<Name>/<id>`; the full "Shop" mega-menu is
populated client-side only and a `/shop` landing page carries no category
or product links in its server HTML, so this spider walks the 6 known,
live category ids rather than attempting (and failing) automatic category
discovery.

Product cards are `div.product-card[data-id]` with the name in a bare
`<h5>` inside the card's own `<a>`, and price in `div.price p.after`
(e.g. " 167  LE"). Pagination is a plain `?page=N` query param; a page's
last page is NOT reliably announced by its own paging-links block (Dairy's
own nav topped out at "page=15" but page=16 still returned 8 more real
products), so this spider pages forward until a page returns zero product
cards rather than trusting the printed page-link list.

Prices are plain EGP amounts with no minor-unit encoding ("167 LE",
"12.95 LE" -- LE = Livre Egyptienne, i.e. EGP), matching countries.yaml.
"""

import re
from datetime import datetime, timezone

import scrapy

_CATEGORIES = {
    "9": "Bakery",
    "20": "Confectionary",
    "6": "Dairy",
    "39": "Metro",
    "25": "Paper-Products",
    "41": "Yameesh",
}
_PRICE_RE = re.compile(r"[\d.,]+")
MAX_PAGES = 60


class MetroMarketsEgSpider(scrapy.Spider):
    name = "metro_markets_eg"
    allowed_domains = ["metro-markets.com"]
    currency = "EGP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _url(self, cat_id: str, page: int) -> str:
        name = _CATEGORIES[cat_id]
        return f"https://www.metro-markets.com/categoryl1/{name}/{cat_id}?page={page}"

    async def start(self):
        for cat_id in _CATEGORIES:
            yield scrapy.Request(
                self._url(cat_id, 1),
                callback=self.parse_category,
                meta={"cat_id": cat_id, "page": 1},
            )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        cards = response.css("div.product-card")
        n = 0
        for card in cards:
            row = self._row(card, _CATEGORIES[cat_id])
            if row:
                n += 1
                yield row
        self.logger.info(
            "metro_markets_eg: category=%s page=%d cards=%d rows=%d",
            _CATEGORIES[cat_id],
            page,
            len(cards),
            n,
        )
        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._url(cat_id, nxt),
                callback=self.parse_category,
                meta={"cat_id": cat_id, "page": nxt},
            )

    def _row(self, card, category: str):
        product_id = card.attrib.get("data-id")
        name = card.css("h5::text").get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        if not product_id or not name:
            return None
        price_text = card.css("div.price p.after::text").get()
        m = _PRICE_RE.search(price_text) if price_text else None
        if not m:
            return None
        price = m.group(0).replace(",", "")
        url = card.css("a::attr(href)").get()
        if not url:
            return None
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
