"""Spider for Food-store.by (Minsk, Belarus) -- https://food-store.by/.

1C-Bitrix storefront (the CIS-region e-commerce platform equivalent to
Shopify/WooCommerce), server-rendered, no WAF hit. Category URLs are
`/catalog/{path}/` (77 leaf categories reachable from the homepage nav);
product cards are `<div class="catalog_item item_wrap" id="bx_<iblock>_<id>">`
with `class="item-title"><a><span>NAME</span>` and a structured
`<div class="price" data-currency="BYN" data-value="PRICE">` attribute
(no text-price parsing needed). Out-of-stock items still carry a price
attribute so they are kept (channel data, not a stock feed).

Re-verified live 2026-08-06: /catalog/bakaleya/krupy_/ris/ -> 200, 8 real
rice SKUs incl. 'Рис Жасмин Bravolli!' BYN 5.00, 'Рис Басмати Села Золотой
шлифованный' BYN 30.25.
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://food-store.by"
_CATEGORY_HREF_RE = re.compile(r'href="(/catalog/[a-z0-9_\-/]+/)"')
_CARD_RE = re.compile(
    r'<div class="catalog_item item_wrap[^"]*" id="bx_\d+_(\d+)">.*?'
    r'class="item-title">\s*<a[^>]*><span>([^<]+)</span>.*?'
    r'class="price" data-currency="([A-Z]{3})" data-value="([\d.]+)"',
    re.S,
)
MAX_PAGES = 30


class FoodstoreBySpider(scrapy.Spider):
    name = "foodstore_by"
    allowed_domains = ["food-store.by"]
    currency = "BYN"
    language = "ru"

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/", callback=self.parse_category, meta={"page": 1}
        )

    def _new_category_requests(self, response):
        for path in _CATEGORY_HREF_RE.findall(response.text):
            if path in self.seen_categories:
                continue
            self.seen_categories.add(path)
            yield scrapy.Request(
                urljoin(_BASE, path),
                callback=self.parse_category,
                meta={"page": 1, "cat_url": urljoin(_BASE, path)},
            )

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = response.url.rstrip("/").rsplit("/", 1)[-1].replace("_", " ")
        n = 0
        for product_id, name, currency, price in cards:
            n += 1
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {response.url} page={page} cards={len(cards)} items={n}"
        )

        cat_url = response.meta.get("cat_url", response.url.split("?")[0])
        if cards and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}PAGEN_1={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )
