"""
Spider for Mubawab Morocco (https://www.mubawab.ma/) - residential rental
listings (COICOP 04.1.1, narrow/source_curated).

Server-rendered listing pages (no Playwright needed) — verified live with
curl_cffi impersonate=chrome124. Each `div.listingBox` card carries the ad id
(`input.adId`), the full untruncated title (`img.sliderImage::attr(alt)` —
the visible `h2.listingTit` text is CSS-ellipsis-truncated with a literal
"..."), and the rent (`span.priceTag`).

Price gotcha confirmed live: `span.priceTag` renders e.g. "10 000 DH" —
a U+202F NARROW NO-BREAK SPACE thousands separator, not a plain space or
non-breaking space (U+00A0). `normalize_price()` (price_scraping.archived)
strips every non [0-9.,-] character before parsing, so it handles this
(and the "1 234,56 Dh" comma-decimal form) without a bespoke regex.

Pagination is NOT a query param — `?page=2` silently re-serves page 1.
The real pattern is a URL path suffix: `<listing-url>:p:<n>:` (confirmed
live: `:p:2:` returns a different first ad than the bare URL).

Scope: residential rental categories only (`appartements-a-louer`,
`villas-et-maisons-de-luxe-a-louer`) across the 10 city slugs Mubawab's own
nav exposes. Commercial/office rental categories are deliberately excluded
— they fall outside COICOP 04.1.1 (actual rentals paid by tenants for
housing) and would make coicop_codes non-narrow.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from ..archived import normalize_price

logger = logging.getLogger(__name__)

# Mubawab's own agents routinely cross-post SALE ads into the rental
# category pages this spider walks (confirmed live 2026-09-01: titles like
# "Appartement spacieux a vendre" and "Duplex a vendre" turned up inside
# /appartements-a-louer and /villas-et-maisons-de-luxe-a-louer, with sale
# prices in the tens of millions of MAD sitting in the same `priceTag`
# field a real rent would occupy). These are the site's own mis-filing, not
# a spider bug -- drop by name since there is no separate "listing type"
# field on the card to key off instead.
_SALE_RE = re.compile(r"\bvente\b|\bvendre\b", re.I)

_CITIES = [
    "casablanca",
    "rabat",
    "marrakech",
    "tanger",
    "agadir",
    "meknes",
    "mohammedia",
    "sal%C3%A9",
    "bouskoura",
    "dar-bouazza",
]
_TYPES = [
    "appartements-a-louer",
    "villas-et-maisons-de-luxe-a-louer",
]


class MubawabMaSpider(scrapy.Spider):
    name = "mubawab_ma"
    allowed_domains = ["mubawab.ma"]
    currency = "MAD"
    language = "fr"
    BASE_URL = "https://www.mubawab.ma/fr/st"
    MAX_PAGES = 40

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for city in _CITIES:
            for ptype in _TYPES:
                base = f"{self.BASE_URL}/{city}/{ptype}"
                yield scrapy.Request(
                    base,
                    callback=self.parse,
                    meta={"page": 1, "base": base, "seen": set(), "ptype": ptype},
                )

    def parse(self, response):
        base = response.meta["base"]
        page = response.meta["page"]
        seen = response.meta["seen"]
        category = self._category(response, response.meta["ptype"])

        cards = response.css("div.listingBox")
        fresh = 0
        for card in cards:
            item = self._item(card, response, category)
            if item is None:
                continue
            if item["product_id"] in seen:
                continue
            seen.add(item["product_id"])
            fresh += 1
            yield item

        if fresh and page < self.MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{base}:p:{nxt}:",
                callback=self.parse,
                meta={
                    "page": nxt,
                    "base": base,
                    "seen": seen,
                    "ptype": response.meta["ptype"],
                },
            )

    @staticmethod
    def _category(response, ptype):
        city_title = response.css("h1::text").get()
        label = "Appartement" if "appartement" in ptype else "Villa/Maison"
        if city_title:
            return f"{label} a louer > {city_title.strip()}"
        return f"{label} a louer"

    def _item(self, card, response, category):
        adid = card.css("input.adId::attr(value)").get()
        price_txt = card.css("span.priceTag::text").get()
        name = card.css("img.sliderImage::attr(alt)").get()
        href = card.attrib.get("linkref")
        if not (adid and price_txt and name and href):
            return None
        if _SALE_RE.search(name):
            return None
        price = normalize_price(price_txt, self.currency)
        if price is None:
            return None
        return {
            "product_id": adid,
            "product_name": name.strip(),
            "category": category,
            "price": float(price),
            "currency": self.currency,
            "available": True,
            "url": href,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
