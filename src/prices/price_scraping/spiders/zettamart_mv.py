"""
Spider for Zettamart (Maldives) — zettamart.com, "Online Grocery Delivery
in Male' & Hulhumale'".

Standard Odoo webshop (`/web/assets/...` builder paths, same platform
family as muexpress_mv). `/shop` listing is server-rendered with
schema.org microdata per card:

    <a itemprop="url" href="/shop/<code>-<slug>-<template_id>">...
    <a itemprop="name" ...>Product Name</a>
    <span itemprop="price" style="display:none;">7.0</span>
    <span itemprop="priceCurrency" style="display:none;">MVR</span>

Newer Odoo theme than muexpress_mv: many CSS classes are prefixed
`oe_product*` (oe_product_cart, oe_product_image, oe_product_image_link,
...), so naively `text.split('class="oe_product"')` (the muexpress_mv
approach) fragments a single card across many pieces and yields zero
matches. Fixed here by running the card regex directly over the full page
with `re.finditer` (order-anchored url -> name -> price -> priceCurrency,
non-overlapping) instead of pre-splitting into per-card chunks.

Pagination is `/shop?page=N`, 24 cards/page. Confirmed pages 1-3 return
disjoint product-template ids (24 unique ids each) — genuine pagination,
not the muexpress-style end-of-catalog clamp, but the same clamp defence
is kept here since Odoo clamps generically.

Page family: listing only (/shop and /shop?page=N) — never visits a PDP.

Verified live 2026-09-11: pages 1-3 (--max-items caps at 24) all yielded
new distinct ids. Sample: "Fresh Red Apple" MVR 9.00, "Felivaru Tuna
Chunks in Oil with Githeyomirus (Hot Chilli) 180g" MVR 25.00.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://zettamart.com"
_MAX_PAGES = 400

_CARD_RE = re.compile(
    r'itemprop="url"[^>]*href="(?P<url>/shop/[^"?]+-(?P<tid>\d+))(?:\?[^"]*)?"'
    r'.*?itemprop="name"[^>]*>(?P<name>[^<]+)<'
    r'.*?itemprop="price"[^>]*>(?P<price>[\d.,]+)<'
    r'.*?itemprop="priceCurrency"[^>]*>(?P<currency>[A-Z]{3})<',
    re.S,
)


class ZettamartMvSpider(scrapy.Spider):
    name = "zettamart_mv"
    allowed_domains = ["zettamart.com"]
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
        logger.error("zettamart_mv: request failed %s — %r", failure.request.url, failure.value)
