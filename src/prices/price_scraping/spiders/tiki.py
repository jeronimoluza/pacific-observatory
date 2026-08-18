"""Scrape Tiki.vn (Vietnam) - https://tiki.vn/

API-first crawl over the seeded consumer-goods category roots.

The listing HTML is no longer parseable: Tiki serves category pages as a
client-rendered shell with no product cards and no `__NEXT_DATA__` payload,
so the previous CSS-card + `__NEXT_DATA__` spider returned zero rows from
2026-08-07 onward. The site's own listing API is open and unauthenticated:

    /api/personalish/v1/blocks/listings?limit=40&category=<id>&page=<n>

It returns `data[]` (id, name, price, url_path) plus a `paging` block with
`last_page` and `total`, so pagination is bounded by the server's own count
rather than by guessing.

GOTCHA -- `paging.total` is CAPPED AT 2000 per category. A root category
reports total=2000/last_page=50 no matter how large it really is, so paging
a root alone silently truncates. This spider therefore descends into a
category's children (via /v2/categories) whenever the category reports the
cap, and pages the children instead.

GOTCHA -- the previous spider's seeded category ids were stale and partly
mislabelled: c8322 was seeded as "Snacks & Candy" but is actually
"Nha Sach Tiki" (the BOOK store), so ~2000 books were being collected under
a confectionery label. Ids here were re-derived on 2026-08-18 from the live
menu-config endpoint.

Bare curl and impersonate=chrome124 both get 403 from tiki.vn as of
2026-08-18 (its TLS fingerprint allowlist moved); chrome131, firefox133 and
safari17_0 all pass. chrome120 -- the project-wide pinned default -- is
also blocked, hence the explicit override.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LISTING = "https://tiki.vn/api/personalish/v1/blocks/listings?limit=40&category={cid}&page={page}"
_CHILDREN = "https://api.tiki.vn/v2/categories?include=children&parent_id={cid}"

# Consumer-goods roots only. Books, electronics, fashion, vehicles, laptops
# and vouchers are deliberately out of scope for a retail price basket.
_ROOTS = [
    (4384, "Bach Hoa Online"),
    (44792, "NGON"),
    (1520, "Lam Dep - Suc Khoe"),
    (15078, "Cham Soc Nha Cua"),
    (2549, "Do Choi - Me & Be"),
]

# paging.total saturates here; treat it as "there is more below this node".
_TOTAL_CAP = 2000
MAX_PAGES = 50
MAX_DEPTH = 2


class TikiSpider(scrapy.Spider):
    name = "tiki"
    allowed_domains = ["tiki.vn", "api.tiki.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.25,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome131"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[int] = set()
        self.seen_cats: set[int] = set()

    async def start(self):
        for cid, name in _ROOTS:
            yield self._listing_request(cid, name, 1, 0)

    def _listing_request(self, cid, name, page, depth):
        return scrapy.Request(
            _LISTING.format(cid=cid, page=page),
            callback=self.parse_listing,
            meta={
                "cid": cid,
                "cat": name,
                "page": page,
                "depth": depth,
                "impersonate": self.IMPERSONATE_PROFILE,
            },
            dont_filter=True,
        )

    def parse_listing(self, response):
        cid = response.meta["cid"]
        name = response.meta["cat"]
        page = response.meta["page"]
        depth = response.meta["depth"]

        try:
            payload = json.loads(response.text)
        except ValueError:
            logger.warning("tiki: unparseable listing JSON for c%s p%s", cid, page)
            return

        rows = payload.get("data") or []
        paging = payload.get("paging") or {}
        scraped_at = datetime.now(timezone.utc).isoformat()

        n = 0
        for prod in rows:
            if not isinstance(prod, dict):
                continue
            pid = prod.get("id")
            pname = prod.get("name")
            price = prod.get("price")
            path = prod.get("url_path")
            if pid is None or not pname or not price or not path:
                continue
            if pid in self.seen_ids:
                continue
            self.seen_ids.add(pid)
            n += 1
            yield {
                "product_id": str(pid),
                "product_name": str(pname).strip()[:500],
                "category": name,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": "https://tiki.vn/" + str(path).lstrip("/"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        total = paging.get("total") or 0
        last_page = paging.get("last_page") or 0
        logger.info(
            "tiki: c%s '%s' page=%d new=%d total=%s last_page=%s depth=%d",
            cid,
            name,
            page,
            n,
            total,
            last_page,
            depth,
        )

        if page < min(last_page, MAX_PAGES):
            yield self._listing_request(cid, name, page + 1, depth)

        # Only the first page of a node decides whether to descend.
        if page == 1 and total >= _TOTAL_CAP and depth < MAX_DEPTH:
            yield scrapy.Request(
                _CHILDREN.format(cid=cid),
                callback=self.parse_children,
                meta={
                    "cid": cid,
                    "depth": depth,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
                dont_filter=True,
            )

    def parse_children(self, response):
        depth = response.meta["depth"]
        try:
            payload = json.loads(response.text)
        except ValueError:
            logger.warning(
                "tiki: unparseable children JSON for c%s", response.meta["cid"]
            )
            return

        for child in payload.get("data") or []:
            if not isinstance(child, dict):
                continue
            child_id = child.get("id")
            child_name = child.get("name")
            if child_id is None or not child_name:
                continue
            if child_id in self.seen_cats:
                continue
            self.seen_cats.add(child_id)
            yield self._listing_request(child_id, str(child_name), 1, depth + 1)
