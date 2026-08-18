"""
Spider for Patuljak.me (Montenegro classifieds) — https://patuljak.me/.

Classifieds/marketplace listing site (schema.org Offer microdata), server-
rendered on the first request per category — `?page=N` query params return
an unhydrated JS placeholder template (all fields empty), but the real
pagination path is `/c/<slug>/namjena-sve/strana-<N>` (0-indexed, confirmed
zero listing overlap between strana-0 and strana-1). Each real card:
  <div class="product__v--l0" itemprop="itemListElement">
    <a itemprop="url" href="/oglas/beko-ves-masina--74892">
      <h5 itemprop="name">Beko veš-mašina</h5></a>
    <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
      <meta itemprop="price" content="100€" />

Eleven top-level categories from the homepage nav; "nekretnine" (real
estate) and "vozila" (vehicles) are by far the largest (nekretnine alone
runs 733 pages / ~16.9k listings at 23 cards/page) so this caps at
MAX_PAGES per category rather than a full crawl — see manifest notes.

Re-verified live 2026-08-17: /c/tehnika -> 200, 23 real cards (electronics/
appliances/tools), 9 total pages; real listing 'Beko veš-mašina' EUR 100
(price content="100€", plain digits, no thousands separator observed even
on 6-figure real-estate listings e.g. content="120000€").
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://patuljak.me"
_TOP_CATEGORIES = [
    "djeciji-svijet",
    "kompjuteri",
    "mobilni-uredjaji",
    "moj-dom",
    "nekretnine",
    "odjeca-i-obuca",
    "sportska-oprema",
    "tehnika",
    "video-igre",
    "vozila",
    "zivotinje",
]
MAX_PAGES = 20

_CARD_RE = re.compile(r'class="product__v--l0" itemprop="itemListElement"')
_NAME_RE = re.compile(
    r'href="(/oglas/[^"]+--(\d+))"[^>]*>\s*(?:<img[^>]*>\s*)?<h5 itemprop="name">([^<]*)</h5>'
)
_PRICE_RE = re.compile(r'itemprop="price" content="([\d.,]*)€?"')
_LAST_PAGE_RE = re.compile(r"strana-(\d+)'>Zadnja")


class PatuljakMeSpider(scrapy.Spider):
    name = "patuljak_me"
    allowed_domains = ["patuljak.me"]
    currency = "EUR"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/c/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 0},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        starts = [m.start() for m in _CARD_RE.finditer(response.text)]
        starts.append(len(response.text))
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i in range(len(starts) - 1):
            card = response.text[starts[i] : starts[i + 1]]
            name_m = _NAME_RE.search(card)
            price_m = _PRICE_RE.search(card)
            if not (name_m and price_m and price_m.group(1)):
                continue
            n += 1
            yield {
                "product_id": name_m.group(2),
                "product_name": html.unescape(name_m.group(3)).strip()[:500],
                "category": slug,
                "price": price_m.group(1),
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, name_m.group(1)),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if page == 0:
            last_m = _LAST_PAGE_RE.search(response.text)
            last_page = min(int(last_m.group(1)), MAX_PAGES) if last_m else 0
            for p in range(1, last_page + 1):
                yield scrapy.Request(
                    f"{_BASE}/c/{slug}/namjena-sve/strana-{p}",
                    callback=self.parse_listing,
                    meta={"slug": slug, "page": p},
                )
