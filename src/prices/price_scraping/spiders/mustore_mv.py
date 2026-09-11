"""
Spider for MU Store (Maldives) — mustore.mv, general grocery/household
online store.

Standard Odoo webshop, same platform family as muexpress_mv and
zettamart_mv. `/shop` listing is server-rendered with schema.org
microdata per card (itemprop="url"/"name"/"price"/"priceCurrency").
Uses the same `re.finditer`-over-full-page approach as zettamart_mv
(not a per-card string split) since this theme also nests
`oe_product*`-prefixed classes that break a naive split.

Pagination is `/shop?page=N`, 20 cards/page. Confirmed pages 1-3 return
disjoint product-template ids.

Page family: listing only (/shop and /shop?page=N) — never visits a PDP.

Note: some prices read implausibly high for the SKU size (e.g. "Lacnor
Milk 1 Ltr" at MVR 380.00) — verified this is what the site itself
displays (not a minor-unit extraction artifact; the rendered
`oe_price`/`oe_currency_value` span shows the same "380.00"), so it is
taken as-is rather than corrected.

Verified live 2026-09-11: pages 1-3 (--max-items caps at 20) all yielded
new distinct ids. Sample: "Parle Black Bourbon Choc 100g" MVR 300.00,
"Apples Bigbucks Gala C135 (18.2Kg)" MVR 680.00.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://mustore.mv"
_MAX_PAGES = 400

_CARD_RE = re.compile(
    r'itemprop="url"[^>]*href="(?P<url>/shop/[^"?]+-(?P<tid>\d+))(?:\?[^"]*)?"'
    r'.*?itemprop="name"[^>]*>(?P<name>[^<]+)<'
    r'.*?itemprop="price"[^>]*>(?P<price>[\d.,]+)<'
    r'.*?itemprop="priceCurrency"[^>]*>(?P<currency>[A-Z]{3})<',
    re.S,
)


class MustoreMvSpider(scrapy.Spider):
    name = "mustore_mv"
    allowed_domains = ["mustore.mv"]
    currency = "MVR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids: set[str] = set()

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page):
        url = f"{_BASE_URL}/shop?page={page}"
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

        new_on_page = 0
        for m in _CARD_RE.finditer(response.text):
            tid = m.group("tid")
            if tid in self._seen_ids:
                continue
            self._seen_ids.add(tid)
            new_on_page += 1
            try:
                price = float(m.group("price").replace(",", ""))
            except ValueError:
                continue
            yield {
                "product_id": tid,
                "product_name": m.group("name").strip(),
                "price": price,
                "currency": m.group("currency"),
                "category": None,
                "url": response.urljoin(m.group("url")),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"{self.name}: page {page} — {new_on_page} new products")

        if new_on_page > 0 and page < _MAX_PAGES:
            yield self._page_request(page + 1)
        else:
            logger.info(f"{self.name}: stopping at page {page} (no new items)")

    def errback(self, failure):
        logger.error("mustore_mv: request failed %s — %r", failure.request.url, failure.value)
