"""
Spider for Guystar (Guyana) -- https://www.guystar.gy/.

Classic Zen Cart storefront (index.php?main_page=index&cPath=<id[_id...]>).
Parent categories only render subcategory boxes, not products (verified
live: cPath=12 "Grocery" returns 0 products, only its subcategory tree) --
products live on leaf categories, so the crawl walks leaf-only cPath ids
extracted from the homepage's nested category menu (185 total path nodes,
154 leaves, listed in _guystar_gy_categories.txt). Each leaf category
renders its product grid directly in server-rendered HTML: name in
`h3.itemTitleFixed > a`, price in `span.productBasePrice`
("GY$<amount>"), product id in the `products_id=<id>` query param on the
same anchor.

Re-verified live 2026-08-06: GET ?main_page=index&cPath=12_261_262 -> 200,
55KB, 13 real products incl. 'Cellophane Bean Thread Noodles Roland 250g'
GY$995. Currency GYD (GY$ prefix) matches countries.yaml. No pagination
markers observed on probed leaf categories (36-product category rendered
in one response) -- a defensive `page=N` follow is still wired in case a
larger leaf paginates.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.guystar.gy"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_guystar_gy_categories.txt"
MAX_PAGES_PER_CATEGORY = 15
_PID_RE = re.compile(r"products_id=(\d+)")


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class GuystarGySpider(scrapy.Spider):
    name = "guystar_gy"
    allowed_domains = ["guystar.gy"]
    currency = "GYD"
    language = "en"

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
        for cpath in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/index.php?main_page=index&cPath={cpath}",
                callback=self.parse_category,
                meta={"cpath": cpath, "page": 1},
            )

    def parse_category(self, response):
        cpath = response.meta["cpath"]
        page = response.meta["page"]
        boxes = response.css("div.centerBoxContentsProducts")
        for box in boxes:
            href = box.css("h3.itemTitleFixed a::attr(href)").get()
            name = box.css("h3.itemTitleFixed a::text").get()
            price_txt = box.css("span.productBasePrice::text").get()
            if not href or not name or not price_txt:
                continue
            pid_match = _PID_RE.search(href)
            if not pid_match:
                continue
            price = re.sub(r"[^\d.]", "", price_txt)
            if not price:
                continue
            yield {
                "product_id": pid_match.group(1),
                "product_name": name.strip(),
                "category": cpath,
                "price": price,
                "currency": self.currency,
                "url": urljoin(_BASE, href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if boxes and page < MAX_PAGES_PER_CATEGORY:
            next_href = response.css('a[href*="page="]::attr(href)').get()
            if next_href:
                yield scrapy.Request(
                    urljoin(_BASE, next_href),
                    callback=self.parse_category,
                    meta={"cpath": cpath, "page": page + 1},
                )
