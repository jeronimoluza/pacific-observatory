"""
Spider for List.am (Armenia) - list.am

Armenia's largest general classifieds marketplace (cars, real estate,
electronics, food, jobs, services, etc). Server-rendered HTML, no JS
execution needed for the listing cards -- but the plain `curl` User-Agent
gets a Cloudflare challenge; `curl_cffi impersonate="chrome124"` clears it
(TLS-fingerprint gate, not a real bot wall).

Each category page (`/en/category/<id>`) paginates with `?n=<page>`
(confirmed distinct listing ids page 1 vs page 2). Cards carry title, price
(amount + currency symbol -- majority AMD "֏", but vehicles/real-estate
frequently list in USD "$", and the symbol can appear before OR after the
amount depending on currency), and category breadcrumb text, all in the raw
HTML.

coicop_classification: classifier (general classifieds, no single COICOP
class applies) -- same treatment as olx_ba/tayara_tn. channel: marketplace
(seller-authored titles).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.list.am"

# Top-level category ids scraped from the site's own nav (Armenian labels
# in comments; English names via /en/ prefix on item pages).
_CATEGORIES = {
    "4": "Electronics",
    "14": "Food and Beverages",
    "16": "Transport",
    "26": "Household Appliances",
    "37": "Animals",
    "39": "Hobby and Sport",
    "54": "Real Estate",
    "65": "Services",
    "84": "Business and Equipment",
    "133": "Home and Garden",
}
MAX_PAGES_PER_CATEGORY = 10

_ITEM_ID_RE = re.compile(r'href="/en/item/(\d+)\?')
_CARD_SPLIT_RE = re.compile(r'(?=href="/en/item/\d+\?)')
_TITLE_RE = re.compile(r'class="pt">([^<]+)<')
_AMOUNT_RE = re.compile(
    r'category-data-list-(?:grid-)?card__amount">'
    r'(?:<span class="category-data-list-(?:grid-)?card__currency">([^<]+)</span>)?'
    r"([\d,\.]+)"
    r'(?:<span class="category-data-list-(?:grid-)?card__currency">([^<]+)</span>)?'
)

_CURRENCY_MAP = {
    "֏": "AMD",
    "$": "USD",
    "€": "EUR",
    "₽": "RUB",
}


class ListAmSpider(scrapy.Spider):
    name = "list_am"
    allowed_domains = ["list.am", "www.list.am"]
    currency = "AMD"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def start_requests(self):
        for cat_id in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/en/category/{cat_id}",
                callback=self.parse_category,
                meta={"category_id": cat_id, "page": 1},
            )

    def parse_category(self, response):
        cat_id = response.meta["category_id"]
        page = response.meta["page"]
        cards = _CARD_SPLIT_RE.split(response.text)[1:]
        logger.info(f"list_am: category={cat_id} page={page} cards={len(cards)}")

        for card in cards:
            id_m = _ITEM_ID_RE.match(card)
            title_m = _TITLE_RE.search(card)
            amount_m = _AMOUNT_RE.search(card)
            if not id_m or not title_m or not amount_m:
                continue
            item_id = id_m.group(1)
            title = title_m.group(1).strip()
            symbol = amount_m.group(1) or amount_m.group(3)
            amount_text = amount_m.group(2).replace(",", "")
            try:
                price = float(amount_text)
            except ValueError:
                continue
            if price <= 0:
                continue
            currency = _CURRENCY_MAP.get(symbol, self.currency)

            yield {
                "product_id": item_id,
                "product_name": title,
                "price": price,
                "currency": currency,
                "category": _CATEGORIES.get(cat_id),
                "url": f"{_BASE}/en/item/{item_id}",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }

        if cards and page < MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/en/category/{cat_id}?n={next_page}",
                callback=self.parse_category,
                meta={"category_id": cat_id, "page": next_page},
            )
