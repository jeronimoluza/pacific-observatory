"""
Brodies (Belize) -- https://brodies.bz/ (pharmacy / drugstore, Belize City).

NOT WordPress/WooCommerce as the sourcing sheet guessed (rule 23 territory --
the sheet's platform column was wrong again). The live site is a GoDaddy
"Simple Store" storefront (`<meta name="generator" content="... Go Daddy
Website Builder 8.0.0000">`) whose real product catalogue lives on a
separate `mysimplestore.com` sub-origin, discovered via a Playwright network
trace of https://brodies.bz/shop:

    https://<store-uuid>.mysimplestore.com/api/v2/products?page=N&per_page=15

No auth, plain JSON, paginates via `pages` in the payload. 61 SKUs total
(4 full pages of 15 + a 1-item last page) confirmed live 2026-09-01 --
Band-Aid, Benadryl, Bengay, Tylenol, Motrin, Imodium, Desitin, reading
glasses/sunglasses. This is a genuine pharmacy/drugstore catalogue, not a
supermarket (the brief's assumption) -- channel is `pharmacy`, so it does
NOT count toward the food tally.

Contact page confirms "4 Albert St, Belize City" and "Copyright (c) 2025
Brodies Store" -- live, current-year business.

Currency: API returns `currency: "USD"` explicitly on every product
("$29.36" etc, no BZ$ prefix anywhere) -- recorded as USD, NOT silently
converted to BZD, per the wave-13 brief's peg trap.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_STORE_ID = "47d773ea-5c80-4654-b764-3d2755162bdb"
_API_BASE = f"https://{_STORE_ID}.mysimplestore.com/api/v2/products"
_PER_PAGE = 15


class BrodiesBzSpider(scrapy.Spider):
    name = "brodies_bz"
    allowed_domains = ["mysimplestore.com", "brodies.bz"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API_BASE}?page=1&per_page={_PER_PAGE}",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("brodies_bz: non-JSON response at %s", response.url)
            return
        products = payload.get("products") or []
        page = response.meta["page"]
        logger.info("brodies_bz page=%s count=%s", page, len(products))
        for p in products:
            item = self._item(p)
            if item:
                yield item
        total_pages = payload.get("pages") or 1
        if page < total_pages:
            nxt = page + 1
            yield scrapy.Request(
                f"{_API_BASE}?page={nxt}&per_page={_PER_PAGE}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict):
        price = (p.get("price") or {}).get("numeric")
        if price is None:
            return None
        name = html.unescape(str(p.get("name") or "")).strip()
        # Fixed-point unescape: WordPress/GoDaddy templates occasionally
        # double-escape entities (&amp;#8211; etc).
        prev = None
        while prev != name:
            prev = name
            name = html.unescape(name)
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            return None
        return {
            "product_id": str(p.get("id") or p.get("ols_product_id") or p.get("slug")),
            "product_name": name[:500],
            "category": None,
            "price": str(price),
            "currency": (p.get("price") or {}).get("currency") or self.currency,
            "available": bool(p.get("available", True))
            and bool(p.get("in_stock", True)),
            "url": f"https://brodies.bz{p.get('relative_url')}"
            if p.get("relative_url")
            else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
