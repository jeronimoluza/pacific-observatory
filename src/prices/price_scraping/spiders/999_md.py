"""
Spider for 999.md — Moldova's largest classifieds marketplace.

Next.js app-router site: category listing pages (/ru/list/<cat>/<subcat>) ship
an unhydrated skeleton in the initial HTTP response (every advert card's title
and price div is empty — confirmed via plain curl, no product data in the
__NEXT_DATA__/RSC stream either), so this is a genuine Playwright render, not
a hidden JSON API (robots.txt disallows /api/ and every guessed REST/GraphQL
path 404s/502s). After `domcontentloaded` + waiting for the first real card
selector, cards render as:
  <a href="/ru/105140383">
    ...<div class="...__advert__photo__title">
      <div class="... advert__title"><h4>iPhone 14 Pro</h4></div></div>
    <div class="...__advert__photo__price">
      <div class="...__price"><div class="...__price__row">
        <span class="...__price__text">8&nbsp;600 MDL</span>
        <span class="...__price__additional__info">...</span>
      </div></div></div></a>
CSS module hash prefixes (e.g. "tcGT3q") change per build, so selectors match
on class *substrings* ("price__text", not the hashed prefix) rather than
exact class names.

This is a classifieds site, not a curated retail catalog: each seller sets
their own price and currency, so per-row currency is parsed from the price
text itself (MDL / EUR "€" / USD "$" all observed), not assumed constant.
Confirmed live 2026-08-17.

Scope: 999.md has hundreds of leaf subcategories; a full crawl is out of
bounds for this pass. Scoped to 7 leaf categories spanning the site's actual
mix — transport/cars and real-estate/apartments-and-rooms (the two dominant
categories by listing volume, per site nav/pagination depth) plus 5 goods
categories (phones, two household-appliance lines, laptops, sofas) — capped
at 6 pages/category (~80 cards/page => ~480 cards/category max, ~3.4k rows
total ceiling before de-dup). See manifest notes for the exact category list.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

_BASE = "https://999.md"

# (leaf path, category label). "transport/cars" and "real-estate/apartments-
# and-rooms" are the two dominant categories on the site by listing volume.
_CATEGORIES = [
    ("transport/cars", "transport/cars"),
    ("real-estate/apartments-and-rooms", "real-estate/apartments-and-rooms"),
    ("phone-and-communication/mobile-phones", "phone-and-communication/mobile-phones"),
    ("household-appliances/refrigerators", "household-appliances/refrigerators"),
    ("household-appliances/washing-machines", "household-appliances/washing-machines"),
    (
        "computers-and-office-equipment/laptops",
        "computers-and-office-equipment/laptops",
    ),
    ("furniture-and-interior/sofas", "furniture-and-interior/sofas"),
]
MAX_PAGES = 6

_CARD_SEL = 'div[data-testid="infinite-ads-list"] a[href^="/ru/"]'
_ID_RE = re.compile(r"/ru/(\d+)")
_PRICE_RE = re.compile(r"([\d ,. ]+)\s*(MDL|EUR|USD|€|\$|лей|леи)", re.IGNORECASE)

_CURRENCY_MAP = {
    "€": "EUR",
    "$": "USD",
    "MDL": "MDL",
    "ЛЕЙ": "MDL",
    "ЛЕИ": "MDL",
    "EUR": "EUR",
    "USD": "USD",
}


def _parse_price(text: str):
    if not text:
        return None, None
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    amount = m.group(1).replace(" ", "").replace(" ", "").replace(",", "")
    amount = amount.rstrip(".")
    if not amount or not amount.replace(".", "", 1).isdigit():
        return None, None
    currency = _CURRENCY_MAP.get(m.group(2).upper())
    if not currency:
        return None, None
    return amount, currency


class NineNineNineMdSpider(scrapy.Spider):
    name = "999_md"
    allowed_domains = ["999.md"]
    currency = "MDL"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "CONCURRENT_REQUESTS": 3,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
    }

    async def start(self):
        for path, label in _CATEGORIES:
            for page_num in range(1, MAX_PAGES + 1):
                suffix = f"?page={page_num}" if page_num > 1 else ""
                url = f"{_BASE}/ru/list/{path}{suffix}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_list,
                    errback=self.errback,
                    meta={
                        "playwright": True,
                        "playwright_page_goto_kwargs": {
                            "wait_until": "domcontentloaded"
                        },
                        "playwright_page_methods": [
                            PageMethod("wait_for_selector", _CARD_SEL, timeout=15000),
                            PageMethod("wait_for_timeout", 800),
                        ],
                        "category": label,
                        "page_num": page_num,
                    },
                )

    def parse_list(self, response):
        category = response.meta["category"]
        page_num = response.meta["page_num"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        yielded = 0
        seen_on_page = set()
        for card in response.css(_CARD_SEL):
            href = card.attrib.get("href")
            if not href:
                continue
            id_m = _ID_RE.search(href)
            if not id_m:
                continue
            product_id = id_m.group(1)
            if product_id in seen_on_page:
                continue
            seen_on_page.add(product_id)

            name = card.css("h4::text").get()
            if not name or not name.strip():
                continue
            name = name.strip()

            price_text = card.css('span[class*="price__text"]::text').get()
            amount, price_currency = _parse_price(price_text)
            if amount is None:
                continue

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": amount,
                "currency": price_currency,
                "available": True,
                "url": urljoin(_BASE, href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1
        logger.info(f"999_md: category={category} page={page_num} yielded={yielded}")

    def errback(self, failure):
        logger.error(
            f"999_md request failed: {failure.request.url} — {failure.value!r}"
        )
