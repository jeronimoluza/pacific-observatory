"""Spider for Mekka Market (Romania) -- https://mekkamarket.ro/.

Mekka Market is a small app-led grocery-delivery storefront running a
white-label "xf" platform (`vendor/xf/assets/...`). Discovery lead (wave 4,
bare hostname `mekkamarket.ro`). Triage AI_NOTES flagged "RON per-buc and
per-kg pricing, but many lines show 0.00 RON - partial catalogue load" --
that pattern is real on *some* category groups but the produce/grocery
groups sampled here are cleanly priced; the spider still drops zero-price
rows defensively per the AI_NOTES guidance.

**Server-rendered, not a SPA**: despite the app-like framing ("Descarca
Aplicatia" banner on the homepage), the `/sys/app/shop/productGroup/?id=...`
pages are plain server-rendered HTML -- a Playwright network trace of one
of these pages fired zero product-data XHRs, and the same product cards
(names, prices) are present verbatim in a bare `curl_cffi` GET. No
Playwright needed at collection time.

**Price format is unusual**: the integer and decimal parts are split across
sibling text/`<sup>` nodes -- `<p class="widget-search-result-price">1<sup>75</sup>
RON / buc</p>` renders as "1,75 RON" (1.75 RON), not "1" and "75" as two
separate values. A naive `[0-9]+[.,][0-9]{2}\\s*RON` regex misses this
entirely (confirmed during probing) -- must match the `<sup>`-split shape.

18 `productGroup` ids were collected from the homepage's own category rail
links (`/sys/app/shop/productGroup/?id=<24-hex-id>`); each group renders
~20 product cards with no visible in-group pagination in the raw HTML.

Page family parsed: `productGroup` (category listing) pages only; the
`/sys/app/shop/product/?id=...` PDP is never fetched.

Test run 2026-09-06 (--max-items 10): passed, real RON prices (e.g. 1.75-
3.18 RON for loose produce), 0 blank names.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://mekkamarket.ro"

_CATEGORY_IDS = [
    "63f5e0553c37273a5d55971e",
    "63fe10cdcb62470fe46cdab8",
    "63fe2ddb250b9714d833a705",
    "63fe2e45f8561b4c637b95c5",
    "63fe2ebcad169b6e4601eed4",
    "63fe2fa8250b9714d833a708",
    "63fe3281e6d00721fe47022d",
    "63fe32bde6d00721fe47022e",
    "63fe32f5e6d00721fe47022f",
    "63fe335df8561b4c637b95d1",
    "63fe339cf8561b4c637b95d2",
    "63fe33ccf675a424b9504be6",
    "63fe3407f8561b4c637b95d4",
    "63fe3531d9046b56a543e00b",
    "63fe35adf675a424b9504beb",
    "63fe361690b7e5559f650775",
    "6404e377e381cf33fd0887a9",
    "6404e4107a4129020c581bbb",
]

_CARD_SPLIT_RE = re.compile(r'(?=<div class="widget-search-result-card">)')
_PRODUCT_ID_RE = re.compile(r"/product/\?id=([0-9a-f]{24})")
_TITLE_RE = re.compile(r'widget-search-result-card-title">([^<]+)</h5>')
_PRICE_RE = re.compile(
    r'widget-search-result-price">\s*([0-9]+)<sup>([0-9]{1,2})</sup>\s*([A-Z]{3})\s*(?:/\s*([a-z]+))?'
)


class MekkamarketRoSpider(scrapy.Spider):
    name = "mekkamarket_ro"
    allowed_domains = ["mekkamarket.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def start_requests(self):
        for cid in _CATEGORY_IDS:
            yield scrapy.Request(
                f"{_BASE}/sys/app/shop/productGroup/?id={cid}",
                callback=self.parse_group,
                meta={"category_id": cid, "impersonate": "chrome124"},
            )

    def parse_group(self, response):
        cid = response.meta["category_id"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for block in _CARD_SPLIT_RE.split(response.text)[1:]:
            pid_m = _PRODUCT_ID_RE.search(block)
            title_m = _TITLE_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not (pid_m and title_m and price_m):
                continue
            name = title_m.group(1).strip()
            if not name:
                continue
            integer_part, decimal_part, currency, unit = price_m.groups()
            try:
                price_val = float(f"{integer_part}.{decimal_part}")
            except ValueError:
                continue
            if price_val <= 0:
                continue

            yield {
                "product_id": pid_m.group(1),
                "product_name": name,
                "price": price_val,
                "currency": currency or self.currency,
                "category": None,
                "unit": unit,
                "url": f"{_BASE}/sys/app/shop/product/?id={pid_m.group(1)}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1

        logger.info(f"mekkamarket_ro: category={cid} yielded={yielded}")
