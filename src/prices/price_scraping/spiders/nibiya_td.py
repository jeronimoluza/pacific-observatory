"""Nibiya (Chad) -- https://nibiya.com/. General classifieds marketplace for
N'Djamena/Tchad (+235 support, FCFA prices, 22 categories).

Laravel + Livewire. The listing component is reachable over plain GET at
/filter-resultats: `?categorieId=<Category>` scopes it and `&page=N`
paginates, both server-rendered (no Livewire XHR needed at collect time).
Enumerability verified 2026-09-12: Automobiles p1/p2/p3 returned 21/18/24
ad links with zero overlap between pages, so this is a real paginating
listing rather than a re-served first page.

Category names come from the homepage nav verbatim (URL-encoded accents
included) -- they are the raw `categorieId` values the filter expects, not
slugs we may normalise. `Alimentation` is NOT one of them: the food category
is spelled `Nouriture` on the site.

Prices are plain integer FCFA in `h6.price-item`. Confirmed XAF (Central
African CFA franc) per countries.yaml's Chad default -- the site renders the
ambiguous "FCFA" string only, so this is the country default rather than a
machine-readable code.

Page family: listing only -- name and price are both on the result card;
ad detail pages are never fetched. Ad URLs are
https://nibiya.com/fr/<Category>/<slug>_<id>.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

# Raw `categorieId` values, taken verbatim (URL-encoded) from the homepage nav.
CATEGORIES = [
    "%C3%89ducations_et_formations",
    "%C3%89lectroniques",
    "Agro-pastorale",
    "Animaux_domestiques",
    "Automobiles",
    "Enfants_et_jouets",
    "Entreprises_%C3%89quipements",
    "Immobilier",
    "Jeux_vid%C3%A9o_et_consoles",
    "La%20mode_des_Hommes",
    "La_mode_des_femmes",
    "Livres_et%20_oisirs",
    "Maison_%26_Jardin",
    "Mobile_tablette",
    "Motocyclettes",
    "Nouriture",
    "Ordinateurs_et_portables",
    "Propri%C3%A9t%C3%A9s_%C3%A0_louer",
    "Services",
    "Sports_et_remise_en_forme",
    "sante",
]
# "Emplois" (job ads) is deliberately excluded -- salaries are not prices.

MAX_PAGES = 25
BASE = "https://nibiya.com/filter-resultats"
_PRICE_RE = re.compile(r"[\d\s.,]+")


class NibiyaTdSpider(scrapy.Spider):
    name = "nibiya_td"
    allowed_domains = ["nibiya.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen: set[str] = set()

    async def start(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"{BASE}?categorieId={cat}&page=1",
                callback=self.parse_listing,
                meta={"cat": cat, "page": 1},
            )

    def parse_listing(self, response):
        cat = response.meta["cat"]
        page = response.meta["page"]
        soup = BeautifulSoup(response.text, "html.parser")
        found = 0
        for card in soup.select("div.product"):
            link = card.select_one('a[href*="nibiya.com/fr/"]')
            details = card.select_one("div.product-details")
            if not link or not details:
                continue
            url = link.get("href", "")
            if "/fr/nouvelle-annonce" in url or "_" not in url.rsplit("/", 1)[-1]:
                continue
            price_el = details.select_one("h6.price-item")
            name_el = details.select_one("p")
            if not price_el or not name_el:
                continue
            name = name_el.get_text(" ", strip=True)
            raw = price_el.get_text(" ", strip=True)
            m = _PRICE_RE.search(raw)
            if not name or not m:
                continue
            price = m.group(0).replace(" ", "").replace(",", "").replace(".", "").strip()
            if not price or int(price) <= 1:
                # `1 FCFA` is the site's placeholder for "price on request".
                continue
            found += 1
            if url in self._seen:
                continue
            self._seen.add(url)
            yield {
                "product_id": url.rsplit("_", 1)[-1],
                "product_name": name[:500],
                "category": cat,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if found and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?categorieId={cat}&page={nxt}",
                callback=self.parse_listing,
                meta={"cat": cat, "page": nxt},
            )
