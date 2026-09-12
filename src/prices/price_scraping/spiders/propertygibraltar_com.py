"""Spider for PropertyGibraltar (https://www.propertygibraltar.com/rentals) --
Gibraltar residential rental listings.

PropertyGibraltar is a Gibraltar-wide rental/sale portal that syndicates the
books of the territory's estate agents (each card carries the listing agent
logo -- BFA, Chesterton, Savills etc.), so one crawl covers the local agency
market rather than a single agent.

Server-rendered Bootstrap HTML, no JS needed: curl_cffi impersonate=chrome124
returns the full card markup (measured 2026-09-11). Listing cards are
`div.property-item`; the price lives in `div.property-info h5.price` as
"GBP 710 pcm" and the PDP link + title in `div.property-info h5 a`.

Card-vs-carousel gotcha: a page holds 22 `div.property-item` nodes but only
20 are listing cards. The other two are the top "featured" banner blocks,
which put their price in an `h4.price` inside a `div.row` and carry no
`div.property-info` at all. Scoping every field under `div.property-info`
drops them cleanly, which is correct -- the featured pair duplicates
listings that also appear in the grid below.

product_id is the numeric suffix of the PDP slug
(`/property/apartment-upper-town-16434` -> 16434), which is the portal's own
listing id and is stable across pages.

Pagination is `?sale=0&category=1&np=N`, 20 cards/page, 14 pages at the time
of onboarding (~280 live rentals). Enumerability confirmed live 2026-09-11:
page 1, page 2 and page 14 return different id sets (p1 vs p2 share 4 of 20
-- the portal floats a few promoted listings onto every page, so the sets
are not disjoint; dedup is by product_id downstream and the crawl stops when
a page repeats the PREVIOUS page exactly, not when it merely overlaps).

Page family parsed: listing only. The `/property/<slug>` PDP url is emitted
but never fetched by this spider.

Currency: the site prints GBP and Gibraltar trades GBP at par with GIP; set
at class level rather than parsed from the symbol. `coicop_codes: ["04.1.1"]`
-- narrow source, residential rentals, monthly pricing basis ("pcm" = per
calendar month).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE = "https://www.propertygibraltar.com"
_LISTING = _BASE + "/rentals?sale=0&category=1&np={page}"
_MAX_PAGES = 20

_ID_RE = re.compile(r"-(\d+)$")
_PRICE_RE = re.compile(r"([\d][\d,]*)")


class PropertygibraltarComSpider(scrapy.Spider):
    name = "propertygibraltar_com"
    allowed_domains = ["propertygibraltar.com"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        yield scrapy.Request(
            _LISTING.format(page=1),
            callback=self.parse_page,
            meta={"page": 1, "prev_ids": frozenset(), "impersonate": "chrome124"},
        )

    def _extract(self, response) -> list[dict]:
        soup = BeautifulSoup(response.text, "html.parser")
        items: list[dict] = []
        for card in soup.select("div.property-item"):
            info = card.select_one("div.property-info")
            if info is None:
                continue  # featured banner block, not a listing card
            link = info.select_one("h5 a[href]")
            price_el = info.select_one("h5.price")
            if link is None or price_el is None:
                continue
            url = link["href"].split("?")[0]
            m = _ID_RE.search(url)
            if not m:
                continue
            pid = m.group(1)

            price_m = _PRICE_RE.search(price_el.get_text(" ", strip=True))
            if not price_m:
                continue  # "POA" / price on application
            price = price_m.group(1).replace(",", "")
            if not price or float(price) <= 0:
                continue

            title = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            sub = info.select_one("h6")
            area = re.sub(r"\s+", " ", sub.get_text(" ", strip=True)).strip() if sub else ""
            feats = info.select_one("ul.features")
            spec = re.sub(r"\s+", " ", feats.get_text(" ", strip=True)).strip() if feats else ""
            # Slug carries the property type ("apartment", "studio", "penthouse").
            slug_type = url.rsplit("/", 1)[-1].split("-")[0].replace("_", " ")
            name = " ".join(p for p in [slug_type.title(), "for rent", title, area, spec] if p)

            items.append(
                {
                    "product_id": pid,
                    "product_name": re.sub(r"\s+", " ", name).strip()[:500],
                    "category": "rentals",
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    "url": url,
                    "language": self.language,
                }
            )
        return items

    def parse_page(self, response):
        page = response.meta["page"]
        prev_ids = response.meta["prev_ids"]

        items = self._extract(response)
        cur_ids = frozenset(it["product_id"] for it in items)
        logger.info("propertygibraltar_com: page=%s items=%s", page, len(items))

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["scraped_at_utc"] = scraped_at
            yield item

        if items and cur_ids != prev_ids and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                _LISTING.format(page=nxt),
                callback=self.parse_page,
                meta={"page": nxt, "prev_ids": cur_ids, "impersonate": "chrome124"},
            )
