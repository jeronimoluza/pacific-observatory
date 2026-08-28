"""
Spider for MegaMarket (Romania) — https://www.megamarket.ro/.

Old-style server-rendered PHP storefront (table-based markup, per-product
`id="p_<id>_..."` widgets). Re-verified live 2026-08-06: category page
/bacanie/conserve/conserve-peste -> 200, 47 real product cards, e.g.
'Merve Hering in Ulei Aromat 170g' 9,74 lei.

The nav embeds the full category tree with per-category item counts
(<a href="https://www.megamarket.ro/<path>" title="...">Name<span>(N)</span>)
which matches the CSV probe's completeness check (conserve=278, paste=53).
Parent category pages only show a curated ~20-item sample; the full catalog
lives at the LEAF category paths, so we walk only the leaves (no other path
in the tree is a prefix of a leaf's path) -- companion file
`_megamarket_ro_categories.txt` (379 leaf paths, extracted from the nav
2026-08-06) mirrors the glomark_lk.py pattern to stay under the 500-line cap.

Page size: the site paginates via a session cookie (not a URL param) set by
GET /_redirects/limp.php?limp=160&ref=<url>, which is the largest option the
site's own page-size selector offers (20/40/80/160). We bootstrap that
cookie once per spider run, then walk each leaf category with the same
Scrapy cookiejar; the site returns everything (leaf categories are all
<160 items in practice). No further pagination link is exposed if a leaf
ever exceeds 160 items -- not observed in this catalog.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.megamarket.ro"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_megamarket_ro_categories.txt"
_LIMP_BOOTSTRAP = f"{_BASE}/_redirects/limp.php?limp=160&ref={_BASE}/"

_TITLE_RE = re.compile(r'class="BoxProdTitle">([^<]+)</a>')
_HREF_RE = re.compile(
    r'href="(https://www\.megamarket\.ro/[a-z0-9/-]+)" class="BoxProdTitle"'
)
_ID_RE = re.compile(r'id="p_(\d+)_shop_votes')
_PRICE_RE = re.compile(r'font-weight:bold;">([\d,]+)</span>\s*lei')


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class MegamarketRoSpider(scrapy.Spider):
    name = "megamarket_ro"
    allowed_domains = ["megamarket.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "COOKIES_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            _LIMP_BOOTSTRAP,
            callback=self.after_bootstrap,
            meta={"cookiejar": "megamarket"},
        )

    def after_bootstrap(self, response):
        for path in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/{path}",
                callback=self.parse_category,
                meta={"cookiejar": "megamarket", "category": path},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        blocks = response.text.split('<div class="BoxProd">')[1:]
        logger.info(f"megamarket_ro: {category} products={len(blocks)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for b in blocks:
            item = self._item(b, category, scraped_at)
            if item:
                yield item

    def _item(self, block: str, category: str, scraped_at: str):
        title_m = _TITLE_RE.search(block)
        href_m = _HREF_RE.search(block)
        id_m = _ID_RE.search(block)
        price_m = _PRICE_RE.search(block)
        if not (title_m and href_m and id_m and price_m):
            return None
        return {
            "product_id": id_m.group(1),
            "product_name": title_m.group(1).strip()[:500],
            "category": category,
            "price": price_m.group(1).replace(",", "."),
            "currency": self.currency,
            "available": True,
            "url": href_m.group(1),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
