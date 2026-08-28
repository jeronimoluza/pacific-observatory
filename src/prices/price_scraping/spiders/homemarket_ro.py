"""
Spider for HomeMarket.ro (Romania) — https://www.homemarket.ro/.

Legacy server-rendered PHP storefront. /sitemap.xml lists 144 category ids
as `index.php?c=<id>` (companion `_homemarket_ro_categories.txt`) plus
~11K individual `product.php?c=<id>&p=<id>` URLs, but the category listing
page is cheaper to walk than 11K product pages: `index.php?c=<id>` renders
20 products per response in a `<ul id="listaproduse">` table, and — despite
having no visible pager link in the HTML — accepts an undocumented
`&page=N` query param that was found by brute-forcing common pagination
param names against a category with 100+ SKUs (`pag`/`p`/`pg`/`start`/
`offset`/`inceput` all returned page 1 again; `page` returned a disjoint
product set). Re-verified live 2026-08-06: c=603 (coffee) page=1..8 return
20 unique products each with zero overlap, page=9 returns 6, page=10
returns 0 -- so we paginate until an empty response.

Each `<li>` row carries product_id (hidden `produs` input), name (both an
`alt=` attribute and an anchor text -- identical in samples, anchor text
used), pack size ("cantitate"), and total price ("prettotal") directly in
the listing HTML. Sample: c=1003 (Coniac si brandy) -> 'alexandrion 5* 40%'
96.57 Lei.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.homemarket.ro"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_homemarket_ro_categories.txt"
MAX_PAGES = 60  # safety cap per category

_CARD_RE = re.compile(
    r'product\.php\?c=(\d+)&amp;p=(\d+)"><img[^>]*alt="([^"]*)"[^>]*/></a></div></td>\s*'
    r'<td width="140"><a href="[^"]*">([^<]*)</a></td>\s*'
    r'<td width="40" class="cantitate">([^<]*)</td>\s*'
    r'<td width="70" class="prettotal\s*">([^<]*)</td>',
    re.S,
)


def _load_category_ids() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class HomemarketRoSpider(scrapy.Spider):
    name = "homemarket_ro"
    allowed_domains = ["homemarket.ro"]
    currency = "RON"
    language = "ro"

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
        for cat_id in _load_category_ids():
            yield scrapy.Request(
                f"{_BASE}/index.php?c={cat_id}&page=1",
                callback=self.parse_page,
                meta={"cat_id": cat_id, "page": 1},
            )

    def parse_page(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"homemarket_ro: c={cat_id} page={page} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for _cat, product_id, alt_name, name, qty, price in cards:
            display_name = (name or alt_name).strip()
            if qty and qty.strip():
                display_name = f"{display_name} {qty.strip()}"
            yield {
                "product_id": product_id,
                "product_name": display_name[:500],
                "category": cat_id,
                "price": price.replace("Lei", "").strip(),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/product.php?c={cat_id}&p={product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/index.php?c={cat_id}&page={nxt}",
                callback=self.parse_page,
                meta={"cat_id": cat_id, "page": nxt},
            )
