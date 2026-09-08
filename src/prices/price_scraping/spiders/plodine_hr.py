"""
Spider for Plodine (Croatia) — https://www.plodine.hr/.

No online shop (`/prodavaonice`/`/supermarketi` are store-locator pages
only), but the site server-renders weekly promotional catalogues under
`/akcije/<id>/<slug>` -- e.g. "Vikend ponuda" (weekend offer), "XXL
tjedan". Each promo page is a plain HTML grid of `article.card` blocks
with product name, quantity/unit text, and price -- no JS required.

Verified live 2026-09-06: /akcije/47/tjedna-ponuda/xxl-tjedan -> 200, 44
`article.card` blocks incl. "Pečeno pile" (roast chicken) EUR 5.49
(regular) / EUR 6.90 (reference "cijena na" price). /akcije/10/vikend-
ponuda -> 11 more. Promo-page URLs are discovered from the homepage nav
(7 distinct `/akcije/...` links found at probe time); this spider seeds
from those plus the homepage itself so newly rotated promo slugs are
picked up on each run.

SCOPE CAVEAT: this is a weekly-promo feed, not a full catalogue -- Plodine
has no reachable per-SKU online store, only rotating promotional pages.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.plodine.hr"
_SEED_PROMOS = [
    "/akcije/10/vikend-ponuda",
    "/akcije/11/pocetak-tjedna",
    "/akcije/47/tjedna-ponuda/xxl-tjedan",
    "/akcije/79/tjedna-ponuda/izdvojeno",
    "/akcije/218/tjedna-ponuda/plodine-card-ponude-i-kuponi",
    "/akcije/246/tjedna-ponuda/back-to-school",
]

_CARD_RE = re.compile(r'<article class="card card--\d+">.*?</article>', re.S)
_TITLE_RE = re.compile(r'<h2 class="card__title">([^<]+)</h2>')
_QTY_RE = re.compile(r'<p class="card__quantity">([^<]*)</p>')
_PRICE_RE = re.compile(r'<strong>([\d.,]+)</strong>\s*€')
_ID_RE = re.compile(r'data-list-add="(\d+)"')


class PlodineHrSpider(scrapy.Spider):
    name = "plodine_hr"
    allowed_domains = ["plodine.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_BASE + "/", callback=self.parse_home)
        for path in _SEED_PROMOS:
            yield scrapy.Request(
                _BASE + path, callback=self.parse_page, meta={"path": path}
            )

    def parse_home(self, response):
        paths = sorted(set(re.findall(r'href="https://www\.plodine\.hr(/akcije/[^"]+)"', response.text)))
        for path in paths:
            if path not in _SEED_PROMOS:
                yield scrapy.Request(
                    _BASE + path, callback=self.parse_page, meta={"path": path}
                )

    def parse_page(self, response):
        path = response.meta["path"]
        cards = _CARD_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for card in cards:
            title_m = _TITLE_RE.search(card)
            price_m = _PRICE_RE.search(card)
            id_m = _ID_RE.search(card)
            if not title_m or not price_m:
                continue
            qty_m = _QTY_RE.search(card)
            pid = id_m.group(1) if id_m else None
            count += 1
            yield {
                "product_id": pid,
                "product_name": title_m.group(1).strip()[:500]
                + (f" {qty_m.group(1).strip()}" if qty_m and qty_m.group(1).strip() else ""),
                "category": path.strip("/").split("/")[-1],
                "price": price_m.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                # Promo cards have no per-product PDP -- append the id as a
                # fragment so DuplicationPipeline's url-based dedup doesn't
                # collapse every card on the page down to one row.
                "url": f"{_BASE}{path}#{pid or count}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"plodine_hr: {path} items={count}")
