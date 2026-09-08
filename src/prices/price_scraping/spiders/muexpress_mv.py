"""
Spider for Mu Express (Maldives) — muexpress.mv, a general online grocery /
household-goods store.

Standard Odoo webshop (`/web/assets/...` builder paths). The `/shop` listing
is server-rendered with clean schema.org microdata per card:

    <a itemprop="url" href="/shop/<slug>-<template_id>">...
    <span itemprop="price" style="display:none;">1200.0</span>
    <span itemprop="priceCurrency" style="display:none;">MVR</span>

Pagination is `/shop?page=N` (also reachable as `/shop/page/N`), 20 cards
per page. Odoo does NOT return an empty page past the end — it CLAMPS to
the last valid page and re-serves the same 8-item set forever (confirmed:
page=1000 and page=1001 return the identical 8 product-template-ids). This
is the same class of bug noted for Magento pagination elsewhere in this
project, so the stopping condition here is "this page's product-template
ids are a subset of everything already seen", not an empty-page check.

Extensive category tree (appliances, baby, food, etc.) confirms a deep,
general catalog — not a stub storefront.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.muexpress.mv"
_MAX_PAGES = 400

_CARD_RE = re.compile(
    r'itemprop="url"[^>]*href="(?P<url>/shop/[^"?]+-(?P<tid>\d+))(?:\?[^"]*)?"'
    r'.*?itemprop="name"[^>]*>(?P<name>[^<]+)<'
    r'.*?itemprop="price"[^>]*>(?P<price>[\d.,]+)<'
    r'.*?itemprop="priceCurrency"[^>]*>(?P<currency>[A-Z]{3})<',
    re.S,
)
_CARD_WINDOW = 6000


class MuexpressMvSpider(scrapy.Spider):
    name = "muexpress_mv"
    allowed_domains = ["muexpress.mv", "www.muexpress.mv"]
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

        # Split on product card boundaries so the regex only spans one card
        # at a time (avoids greedily matching across card gaps).
        cards = response.text.split('class="oe_product"')[1:]
        new_on_page = 0
        for card_html in cards:
            m = _CARD_RE.search(card_html[:_CARD_WINDOW])
            if not m:
                continue
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

        # Odoo clamps past the last page and re-serves the same set forever;
        # stop as soon as a page contributes nothing new.
        if new_on_page > 0 and page < _MAX_PAGES:
            yield self._page_request(page + 1)
        else:
            logger.info(f"{self.name}: stopping at page {page} (no new items)")

    def errback(self, failure):
        logger.error("muexpress_mv: request failed %s — %r", failure.request.url, failure.value)
