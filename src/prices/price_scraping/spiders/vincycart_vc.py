"""
Spider for VincyCart (St Vincent and the Grenadines) — vincycart.com, an
online grocery-delivery store ("Order groceries for loved ones in St
Vincent & the Grenadines").

Plain server-rendered HTML (custom PHP/Laravel app — a `_token` CSRF field
is present on the add-to-cart form but not required for GET browsing; no
anti-bot). Product cards (`div.vertical-product-card`) each carry:

    <a href=".../products/<slug>" class="card-title ...">NAME</a>
    <span class="fw-bold h4 text-danger">EC$7.99</span>
    <input type="hidden" name="product_variation_id" value="183">

Prices are in EC$ (XCD, East Caribbean dollar — matches countries.yaml for
st_vincent_and_the_grenadines).

Pagination is plain `/products?page=N`. The full catalog is small — the
page's own "Showing 1-9 of 34 results" caption confirms only 34 SKUs total
(verified 2026-09-06) — so this walks `/products?page=N` directly (no
category filtering needed) until a page contributes no new product ids.
St Vincent had exactly one prior source (ckgreaves_vc) before this pass.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://vincycart.com"
_MAX_PAGES = 30

_CARD_RE = re.compile(
    r'href="(?P<url>https://vincycart\.com/products/[^"?]+)"\s+class="card-title'
    r'.*?>(?P<name>[^<]+?)\s*</a>'
    r'.*?class="fw-bold h4 text-danger">EC\$(?P<price>[\d.,]+)<'
    r'.*?name="product_variation_id"\s+value="(?P<pid>\d+)"',
    re.S,
)
_CARD_WINDOW = 4000


class VincycartVcSpider(scrapy.Spider):
    name = "vincycart_vc"
    allowed_domains = ["vincycart.com"]
    currency = "XCD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids: set[str] = set()

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page):
        url = f"{_BASE_URL}/products?page={page}"
        return scrapy.Request(
            url,
            callback=self.parse_page,
            errback=self.errback,
            meta={"page": page},
            dont_filter=True,
        )

    def parse_page(self, response):
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        cards = response.text.split('class="vertical-product-card')[1:]
        new_on_page = 0
        for card_html in cards:
            m = _CARD_RE.search(card_html[:_CARD_WINDOW])
            if not m:
                continue
            pid = m.group("pid")
            if pid in self._seen_ids:
                continue
            self._seen_ids.add(pid)
            new_on_page += 1
            try:
                price = float(m.group("price").replace(",", ""))
            except ValueError:
                continue
            yield {
                "product_id": pid,
                "product_name": m.group("name").strip(),
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": m.group("url"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"{self.name}: page {page} — {new_on_page} new products")

        if new_on_page > 0 and page < _MAX_PAGES:
            yield self._page_request(page + 1)
        else:
            logger.info(f"{self.name}: stopping at page {page} (no new items)")

    def errback(self, failure):
        logger.error("vincycart_vc: request failed %s — %r", failure.request.url, failure.value)
