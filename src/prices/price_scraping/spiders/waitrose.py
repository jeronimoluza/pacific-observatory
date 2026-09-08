"""Spider for Waitrose (United Kingdom) -- https://www.waitrose.com/.

Waitrose is a premium-tier UK supermarket (John Lewis Partnership).
Discovery lead (wave 4, bare hostname `waitrose.com`, triage Verdict
"SUSPECT", AI_NOTES: "Premium tier" -- no further detail).

**Homepage is a dead end, department pages are not**: `www.waitrose.com/`
carries only `window.__PRELOADED_STATE__` app-bootstrap defaults (empty
cart/auth state, no catalogue) -- but the nav's `/ecom/shop/browse/<dept>`
paths (`groceries`, `entertaining`, `offers`) are plain server-rendered
product-grid pages with real prices, reachable via `curl_cffi
impersonate=chrome124` and **no postcode/branch selection required**. This
mirrors the morrisons.com finding in the same wave: both cleared where
Tesco/ASDA/Ocado (same wave) did not.

**Selectors**: each product tile is an `<article data-testid="product-pod"
data-product-id="N" data-product-name="...">` -- id and name are both
attributes on the tile itself, no text-node parsing needed. Price sits a
short distance inside the tile behind `data-test="product-pod-price"`,
nested in a `<span class="redText___...">£D.DD</span>` -- not immediately
adjacent to the attribute, so the price regex needs a bounded lookahead
window rather than a direct match.

Roughly 3 of every 4 tiles on `/ecom/shop/browse/groceries` are promotional
banner cards (no `product-pod-price`, e.g. "Save 1/3" tiles) rather than
real product pods -- the spider silently skips any tile missing a price,
which is expected and not a signal of breakage.

Page family parsed: department listing pages only (name + price both come
from the grid; PDP never fetched). Only `groceries` and `offers` are wired
up (`entertaining` was tried and yields 0 -- an editorial/landing page with
no product-pod tiles); the full Waitrose department nav is much larger and
worth widening later.

Test run 2026-09-06 (--max-items 10): passed, real GBP prices (e.g.
£1.95-£30.50), 0 blank names, matches the rendered page.
"""

from __future__ import annotations

import html as _html
import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.waitrose.com"
_DEPARTMENTS = ["groceries", "offers"]

_BLOCK_SPLIT_RE = re.compile(r'(?=data-testid="product-pod")')
_ID_RE = re.compile(r'data-product-id="([^"]+)"')
_NAME_RE = re.compile(r'data-product-name="([^"]+)"')
_PRICE_RE = re.compile(r'data-test="product-pod-price".{0,200}?£([0-9]+\.[0-9]{2})', re.S)
_HREF_RE = re.compile(r'href="(/ecom/products/[^"]+)"')


class WaitroseSpider(scrapy.Spider):
    name = "waitrose"
    allowed_domains = ["waitrose.com"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
        "DOWNLOAD_TIMEOUT": 45,
    }

    def start_requests(self):
        for dept in _DEPARTMENTS:
            yield scrapy.Request(
                f"{_BASE}/ecom/shop/browse/{dept}",
                callback=self.parse_department,
                meta={"dept": dept, "impersonate": "chrome124"},
            )

    def parse_department(self, response):
        dept = response.meta["dept"]
        yielded = 0
        for block in _BLOCK_SPLIT_RE.split(response.text)[1:]:
            id_m = _ID_RE.search(block)
            name_m = _NAME_RE.search(block)
            price_m = _PRICE_RE.search(block)
            href_m = _HREF_RE.search(block)
            if not (id_m and name_m and price_m and href_m):
                continue
            try:
                price_val = float(price_m.group(1))
            except ValueError:
                continue
            if price_val <= 0:
                continue
            name = _html.unescape(name_m.group(1)).strip()
            if not name:
                continue

            yield {
                "product_id": id_m.group(1),
                "product_name": name,
                "price": price_val,
                "currency": self.currency,
                "category": dept,
                "url": _BASE + href_m.group(1),
                "language": self.language,
                "scraped_at_utc": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1

        logger.info(f"waitrose: {dept} yielded={yielded}")
