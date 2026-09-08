"""
Spider for Thulo.com — https://thulo.com.np/.

Multi-vendor grocery marketplace (each product card names its own named
seller storefront -- e.g. "Pasal 101" at pasal101.thulo.com.np -- and a
seller location, e.g. "Lalitpur"), NOT a single first-party retailer.
Custom Laravel-templated storefront.

The `/supermarket` landing page immediately fetches
`/thulo-product/shop?category=394&maxp=35670` (394 = the "Supermarket"
top-level category id, hardcoded client-side; no separate category-list
endpoint was found via Playwright network capture). That endpoint,
despite being loaded as a page navigation, returns `application/json`
with a single `grid` key holding an HTML fragment string -- plain
`requests`/curl_cffi with no special headers gets the same JSON.

Verified live 2026-09-06: page=1 -> 22 `productPrice` cards, e.g. "Maghe
Special Combo Set 3" रू 2810, seller "Pasal 101" / Lalitpur. `&page=N`
paginates a real, deep catalog (distinct product sets confirmed pages
1-32); the feed runs dry between page 80 and 120 (page 80 still had 8
distinct products, page 120 had 0) -- this spider stops at the first
empty page rather than a hardcoded cap. Matches AI_NOTES's "31 pages of
supermarket lines" as a conservative undercount of the true depth.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://thulo.com.np"
_CATEGORY_ID = 394
_MAXP = 35670
_MAX_PAGES = 150

_HREF_RE = re.compile(r'href="(https://[a-z0-9.]+\.thulo\.com\.np/shop/product/[^"]+)"')
_TITLE_RE = re.compile(r'card-contents-title[^"]*">\s*<a href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>')
_PRICE_RE = re.compile(r'class="offerPrice">रू\s*([\d,]+)')
_SELLER_RE = re.compile(r'href="https://([a-z0-9.]+)\.thulo\.com\.np"[^>]*>\s*<img')


class ThuloComNpSpider(scrapy.Spider):
    name = "thulo_com_np"
    allowed_domains = ["thulo.com.np"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._page_request(page=1)

    def _page_request(self, page):
        return scrapy.Request(
            f"{_BASE}/thulo-product/shop?category={_CATEGORY_ID}&maxp={_MAXP}&page={page}",
            callback=self.parse_page,
            meta={"page": page},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except Exception as exc:
            logger.warning(f"thulo_com_np: page={page} not JSON: {exc}")
            return
        grid = data.get("grid", "")
        # Split into per-product blocks on the price marker so name/price/
        # url are matched from the same card.
        blocks = grid.split('class="singleProduct"')[1:]
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for block in blocks:
            title_m = _TITLE_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not title_m or not price_m:
                continue
            url, name = title_m.groups()
            pid = url.rstrip("/").rsplit("/", 1)[-1]
            count += 1
            yield {
                "product_id": pid,
                "product_name": html.unescape(name.strip())[:500],
                "category": None,
                "price": price_m.group(1).replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"thulo_com_np: page={page} items={count}")

        if count > 0 and page < _MAX_PAGES:
            yield self._page_request(page=page + 1)
