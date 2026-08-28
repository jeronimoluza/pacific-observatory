"""
Spider for mytime.de (Germany) — https://www.mytime.de/.

Custom PHP storefront, server-rendered category pages
(`/<slug>_<id>.html?page=N`). Each product is a `<li class="product-card"
data-listitemid="<id>__0_">` block carrying the permalink
(`/<slug>_<id>.html`), name (`product-card__name__link`), weight
(`product-card__weight`) and current price (`product-card__price--current`)
directly in the raw HTML -- no rendering needed.

Re-verified live 2026-08-06: GET /aepfel_210002501.html -> 200, 350KB, 8
product cards incl. 'Apfel Elstar' (2 kg) 4,09 EUR, 'Apfel Pink Lady'
0,82 EUR. Pagination footer reads "Seite 1 von 1" here; other categories
paginate via `?page=N`, walked until an empty page.

The homepage nav exposes 450 category slugs (`_mytime_de_categories.txt`),
spanning the full assortment (fresh produce through household/pet).
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.mytime.de"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_mytime_de_categories.txt"
_CARD_ID_RE = re.compile(r'data-listitemid="(\d+)__')
_HREF_NAME_RE = re.compile(
    r'href="(/[a-z0-9_-]+\.html)" class="product-card__name__link">\s*([^<]+?)\s*</a>'
)
_WEIGHT_RE = re.compile(r'class="product-card__weight">([^<]+)</small>')
_PRICE_RE = re.compile(
    r'class="product-card__price--current"[^>]*>\s*<strong[^>]*>\s*([0-9.,]+)\s*€'
)
MAX_PAGES_PER_CATEGORY = 30  # safety cap


def _load_categories():
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class MytimeDeSpider(scrapy.Spider):
    name = "mytime_de"
    allowed_domains = ["mytime.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/{slug}?page=1",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        text = response.text
        card_ids = list(_CARD_ID_RE.finditer(text))
        if not card_ids:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for i, m in enumerate(card_ids):
            start = m.end()
            end = card_ids[i + 1].start() if i + 1 < len(card_ids) else len(text)
            chunk = text[start:end]
            href_name = _HREF_NAME_RE.search(chunk)
            price_m = _PRICE_RE.search(chunk)
            if not href_name or not price_m:
                continue
            href, name = href_name.groups()
            weight_m = _WEIGHT_RE.search(chunk)
            product_name = name.strip()
            if weight_m:
                product_name = f"{product_name} ({weight_m.group(1).strip()})"
            price = price_m.group(1).replace(".", "").replace(",", ".")
            count += 1
            yield {
                "product_id": m.group(1),
                "product_name": product_name[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{href}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"mytime_de: {slug} page={page} items={count}")
        if count >= 20 and page < MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/{slug}?page={next_page}",
                callback=self.parse_page,
                meta={"slug": slug, "page": next_page},
            )
