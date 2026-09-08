"""Spider for Dedeman (Romania) -- https://www.dedeman.ro/.

Dedeman is Romania's largest hardware/home-improvement chain, on a Magento 2
storefront. Discovery lead (wave 4, bare hostname `dedeman.ro`, triage tier
"C - engineering required" / Verdict "Directory/report"). Re-probed
2026-09-06: no anti-bot encountered, `curl_cffi impersonate=chrome124`
clears every request 200, category grids and PDPs are fully server-rendered
HTML (classic Magento 2 `product-item` markup, `data-price-amount`
attributes, no JS execution needed).

**Category tree comes free from the homepage nav**: 394 `/c/<id>` category
URLs are linked directly in the homepage's mega-menu HTML (no sitemap or
API call needed) -- `CrawlSpider` + `LinkExtractor` follows them and the
plain product-detail-page links (`/p/<id>`) it finds along the way.

**Price-selection trap (Magento discount markup)**: this theme wraps the
*active* selling price in either `<span class="special-price">` (item is on
sale -- the crossed-out original sits in a sibling `<span class="old-price">`)
or `<span class="final-price">` (no discount -- this is the only price
span). The `data-price-type` attribute is **not** reliable for telling
these apart: a plain, non-discounted item's only price is still tagged
`data-price-type="oldPrice"` in this theme, which reads backwards if you
match on the attribute alone. The correct signal is the wrapper *class*:
prefer `special-price` when present, else `final-price`; the `old-price`
wrapper (crossed-out original) is always skipped.

**No pagination observed** on sampled categories (`aragazuri/c/1153`,
`gresie-si-faianta/c/1068`) -- `?p=2` re-serves the identical product set
(no pager markup in the raw HTML either), so categories appear to render
their full product list on one page. The crawl relies on breadth across
394 categories rather than depth within one.

Page family parsed: category listing pages (`/c/<id>`), which is where both
name and price are extracted -- the spider does not need to visit PDPs at
all since the grid already carries `data-price-amount`.

Test run 2026-09-06 (--max-items 10): passed, real RON prices (e.g.
799.00-1969.00 lei), 0 blank names, matches the rendered page.
"""

from __future__ import annotations

import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

_PRODUCT_ITEM_SPLIT_RE = re.compile(r'(?=<div class="product-item-info")')
_LINK_NAME_RE = re.compile(
    r'<a class="product-item-link" href="([^"]+)">([^<]+)</a>'
)
_PRICE_BOX_RE = re.compile(r'data-price-box="product-id-(\d+)"')
_ACTIVE_PRICE_RE = re.compile(
    r'class="(?:special-price|final-price)">.*?data-price-amount="([\d.]+)"',
    re.S,
)


class DedemanRoSpider(CrawlSpider):
    name = "dedeman_ro"
    allowed_domains = ["dedeman.ro"]
    start_urls = ["https://www.dedeman.ro/ro/"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_TIMEOUT": 30,
        "DEPTH_LIMIT": 2,
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/ro/[a-z0-9\-/]+/c/\d+$",
                deny=r"(cart|checkout|account|login|wishlist|search|dededeal|suport-clienti)",
            ),
            callback="parse_category",
            follow=True,
        ),
    )

    def parse_category(self, response):
        category_name = response.url.rstrip("/").rsplit("/c/", 1)[0].rsplit("/", 1)[-1]
        yielded = 0
        for block in _PRODUCT_ITEM_SPLIT_RE.split(response.text)[1:]:
            link_m = _LINK_NAME_RE.search(block)
            box_m = _PRICE_BOX_RE.search(block)
            if not (link_m and box_m):
                continue
            price_m = _ACTIVE_PRICE_RE.search(block[box_m.end() : box_m.end() + 1200])
            if not price_m:
                continue
            try:
                price_val = float(price_m.group(1))
            except ValueError:
                continue
            if price_val <= 0:
                continue

            url, name = link_m.group(1), link_m.group(2).strip()
            if not name:
                continue

            yield {
                "product_id": box_m.group(1),
                "product_name": name,
                "price": price_val,
                "currency": self.currency,
                "category": category_name,
                "url": url,
                "language": self.language,
                "scraped_at_utc": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1

        logger.info(f"dedeman_ro: {response.url} yielded={yielded}")
