"""Spider for Happy Center (Turkey) -- https://www.happycenter.com.tr/.

Custom PHP storefront, server-rendered. Category nav under `<nav id="anaMenu">`
carries `<li><a href="/{Category}/{Subcategory}">...` entries (65 leaf
subcategories); each subcategory page paginates via `?page=N` with disjoint
product ids per page (confirmed: page 1 vs page 2 have zero id overlap).
Product cards are `<div class="urun" ...><div class="price"><a>PRICE</a>
...<img title="NAME" ...>`. Prices use Turkish decimal-comma formatting
("60,95"). Stops paginating a category once a page returns 0 product cards
or repeats a page's product-id set (defends against an unbounded loop if the
site keeps re-serving the last page past its real end).

Re-verified live 2026-08-06: /Kuru_Gıda/Çay_-_Şeker_-_Bakliyat_-_Un_-_Makarna
-> 200, 26 real product cards incl. 'Balküpü Küp Şeker Gold 1000 gr' TRY
60,95.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.happycenter.com.tr"
_NAV_RE = re.compile(r'<li><a href="(/[^"]+)">([^<]+)</a></li>')
_CARD_RE = re.compile(
    r'urun-id="(\d+)".*?<div class="price">\s*<a[^>]*>([\d.,]+)</a>.*?'
    r'title="([^"]+)"',
    re.S,
)
MAX_PAGES = 40


class HappycenterTrSpider(scrapy.Spider):
    name = "happycenter_tr"
    allowed_domains = ["happycenter.com.tr"]
    currency = "TRY"
    language = "tr"

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

    async def start(self):
        yield scrapy.Request(f"{_BASE}/", callback=self.parse_nav)

    def parse_nav(self, response):
        seen = set()
        for path, _name in _NAV_RE.findall(response.text):
            if path in seen:
                continue
            seen.add(path)
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_category,
                meta={"category_path": path, "page": 1, "prev_ids": frozenset()},
            )

    def parse_category(self, response):
        category = response.meta["category_path"].strip("/").replace("_", " ")
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        ids = frozenset(c[0] for c in cards)
        if not ids or ids == response.meta["prev_ids"]:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, price_raw, name in cards:
            price = price_raw.replace(".", "").replace(",", ".")
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}{response.meta['category_path']}?page={page + 1}",
                callback=self.parse_category,
                meta={
                    "category_path": response.meta["category_path"],
                    "page": page + 1,
                    "prev_ids": ids,
                },
            )
