"""BMS Online (Botswana) -- https://bmsonline.co.bw/store.

Botswana stationery / school-supply and general retailer. Custom Laravel
storefront, NOT one of the generic platforms: no WooCommerce Store API, no
Shopify products.json, no Magento REST, no VTEX, no product sitemap. The
store grid is fully server-rendered with the price already inlined as text,
so this is Tier 1A over plain HTTP -- no Playwright at collect time.

GOTCHA 1 -- lxml cannot parse this page. The template emits a SECOND
`<!DOCTYPE html><html><head>` inside its own <head>, and lxml (and therefore
`response.css` / parsel) truncates the tree at that point: it sees 170 nodes
and an 8.9 KB body out of a 76 KB page, and every product selector returns
zero. The exact same selectors return all 20 cards under BeautifulSoup's
`html.parser`, which is what this spider uses. A `response.css` rewrite here
will silently collect nothing while still reporting HTTP 200.

GOTCHA 2 -- the pagination links the page renders drop the allCats=1 query
param (they point at /store?page=N, the single-category view). This spider
builds its own ?allCats=1&page=N urls rather than following those links,
which is what keeps the crawl on the all-categories catalog.

Enumerability verified live 2026-09-12: /store?allCats=1&page=N returns 20
cards per page for pages 1..49 and 13 on page 50 (~993 products); page 100
returns an empty grid. Pages 1, 2 and 3 return DISJOINT product sets
("A4, WHITE BOARD" vs "BATTERIES DURACELL AAA PKT 16" vs "BEANIE - UNIFORM
NORTHSIDE PRIMARY"), so it paginates rather than re-serving one page.

Card markup (stable, non-hashed class names):
  div.product > a[href]        -> PDP url
    p.product-category         -> category, e.g. "BOOKS"
    span.product-name          -> product name
    h4.product-price           -> "BWP 21.00"

Currency is read from the literal "BWP" prefix the site renders in the price
text, not assumed from countries.yaml.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE = "https://bmsonline.co.bw"
MAX_PAGES = 60  # catalog ends at 50; the empty-grid guard stops earlier
_PRICE_RE = re.compile(r"([A-Z]{3})?\s*([0-9][0-9, ]*(?:\.[0-9]{1,2})?)")


class BmsBwSpider(scrapy.Spider):
    name = "bms_bw"
    allowed_domains = ["bmsonline.co.bw"]
    currency = "BWP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/store?allCats=1&page=1",
            callback=self.parse_grid,
            meta={"page": 1},
        )

    @staticmethod
    def _text(node, selector):
        found = node.select_one(selector)
        return found.get_text(strip=True) if found else None

    def parse_grid(self, response):
        page = response.meta["page"]
        # html.parser, NOT response.css -- see GOTCHA 1 in the module docstring.
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div.product")
        n = 0
        for card in cards:
            name = self._text(card, "span.product-name")
            price_text = self._text(card, "h4.product-price")
            if not name or not price_text:
                continue
            match = _PRICE_RE.search(price_text)
            if not match:
                continue
            anchor = card.select_one("a[href]")
            url = response.urljoin(anchor["href"]) if anchor else response.url
            n += 1
            yield {
                "product_name": name,
                "category": self._text(card, "p.product-category"),
                "price": match.group(2).replace(",", "").replace(" ", ""),
                "currency": match.group(1) or self.currency,
                "url": url,
                "product_id": url.rstrip("/").rsplit("/", 1)[-1] or None,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name} page={page} cards={len(cards)} rows={n}")
        if n and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/store?allCats=1&page={page + 1}",
                callback=self.parse_grid,
                meta={"page": page + 1},
            )
