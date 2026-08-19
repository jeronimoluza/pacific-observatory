"""
Spider for IGA Shop Online (Australia) — https://www.igashop.com.au/.

IGA is a banner group of independently priced/stocked stores; this spider is
scoped to ONE representative store — "Stonemans Village IGA", Kennington VIC
(storeId=32600, slug=iga-kennington, the store named in onboarding) — not
the whole banner. A different store would need its own storeId.

The Next.js front-end calls a plain, unauthenticated JSON API on the same
host (sniffed via Playwright network trace, confirmed with curl):
  - /api/storefront/stores/{storeId}/categoryHierarchy -> full category tree
  - /api/storefront/stores/{storeId}/search?q=<term>&take=N&skip=N -> product
    search, real backend is storefrontgateway.igashop.com.au (revealed via
    the response's _links.self.href)

There is no per-category listing endpoint that returned data cleanly in
probing (a Category facet filter 400'd), so this walks every LEAF category
display name from categoryHierarchy as a free-text search term instead —
noisy (full-text match, so search results overlap across leaves) but the
JSON output is deduplicated here by productId, and downstream dedup handles
any residual overlap. Currency and prices are plain decimal AUD
("priceNumeric": 7.3 for "A2 Full Cream Milk" 2L, matches the rendered
$7.30) — no minor-unit rescaling needed on this platform.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

STORE_ID = "32600"
STORE_SLUG = "iga-kennington"
BASE = f"https://www.igashop.com.au/api/storefront/stores/{STORE_ID}"
TAKE = 50
MAX_ITEMS_PER_TERM = 100  # cap pagination per search term (2 pages)


class IgashopAuSpider(scrapy.Spider):
    name = "igashop_au"
    allowed_domains = ["www.igashop.com.au"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{BASE}/categoryHierarchy",
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.warning(f"igashop_au: non-JSON categoryHierarchy at {response.url}")
            return
        leaves: list[str] = []

        def walk(node):
            children = node.get("children") or []
            if not children:
                if node.get("displayName"):
                    leaves.append(node["displayName"])
            else:
                for c in children:
                    walk(c)

        for top in tree.get("children") or []:
            walk(top)
        logger.info(f"igashop_au: {len(leaves)} leaf categories found")
        for term in leaves:
            yield self._search_request(term, skip=0)

    def _search_request(self, term, skip):
        url = f"{BASE}/search?q={quote(term)}&take={TAKE}&skip={skip}"
        return scrapy.Request(
            url,
            callback=self.parse_search,
            meta={"term": term, "skip": skip},
        )

    def parse_search(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"igashop_au: non-JSON search response at {response.url}")
            return
        items = payload.get("items") or []
        term = response.meta["term"]
        skip = response.meta["skip"]
        logger.info(f"igashop_au: term={term!r} skip={skip} count={len(items)}")
        for it in items:
            record = self._item(it)
            if record:
                yield record
        next_skip = skip + TAKE
        if len(items) >= TAKE and next_skip < MAX_ITEMS_PER_TERM:
            yield self._search_request(term, next_skip)

    def _item(self, it: dict):
        pid = it.get("productId") or it.get("sku")
        if not pid or pid in self.seen_ids:
            return None
        name = (it.get("name") or "").strip()
        price = it.get("priceNumeric")
        if not name or price is None:
            return None
        self.seen_ids.add(pid)
        default_cat = (it.get("defaultCategory") or [{}])[0]
        category = default_cat.get("categoryBreadcrumb")
        return {
            "product_id": str(pid),
            "product_name": name[:500],
            "price": str(price),
            "currency": self.currency,
            "category": category,
            "available": bool(it.get("available", True)),
            "url": f"https://www.igashop.com.au/product/{_slugify(name)}-{pid}?store={STORE_SLUG}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }


def _slugify(name: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug
