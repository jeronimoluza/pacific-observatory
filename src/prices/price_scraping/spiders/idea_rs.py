"""Spider for IDEA (Serbia) -- https://online.idea.rs/.

IDEA is one of Serbia's largest supermarket chains (part of the same
retail group as the Roda and Mercator-S banners -- idea.rs, roda.rs and
mercator-s.rs all cross-link the same store-network announcements. Only
IDEA is onboarded this wave; Roda/Mercator-S were not chased further given
the same-operator risk in rule 10 -- worth confirming with a product-id
overlap check before ever onboarding them too).

`online.idea.rs` is a hash-routed SPA (`/#!/`) with no product data in the
raw HTML shell. Playwright network capture found an "mStart"-family
grocery e-commerce backend (`session/init` reports
`machine_hostname: shop2-prod.mstart.local`, a platform shape also seen at
other Balkan grocers) exposing a clean, cookie-gated but unauthenticated
JSON API:

  GET /session/init                          -- sets session cookies (must
                                                 be called once per session
                                                 before anything else 200s;
                                                 skipping it -> 406)
  GET /v2/categories                         -- full nested category tree
  GET /v2/categories/{id}/products?page=<N>  -- paginated products
                                                 (`_page.page_count`; page N
                                                 vs N-1 confirmed disjoint
                                                 ids)

221 category nodes carry `has_products: true` (mix of true leaves and
parent hubs that also list a few directly-attached products); the spider
walks all of them and dedupes by product id via the DuplicationPipeline
(same "visit hubs too, they just yield extra dupes" pattern as silpo_ua).

Price is `price.amount` in MINOR units (e.g. 59999 -> 599,99 Din, matches
the API's own `formatted_price` field) -- divide by 100, do not treat as a
whole-currency-unit price (rule 11's minor-unit trap). Currency is
reported as the string "Din" in the payload, not an ISO code -- mapped to
RSD (Serbian Dinar, 2 decimals) at the spider level.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://online.idea.rs"
_HEADERS = {"Accept": "application/json", "Referer": f"{_BASE}/"}


def _collect_category_ids(nodes: list[dict], out: list[int]) -> None:
    for n in nodes:
        if n.get("has_products"):
            out.append(n["id"])
        _collect_category_ids(n.get("children") or [], out)


class IdeaRsSpider(scrapy.Spider):
    name = "idea_rs"
    allowed_domains = ["online.idea.rs"]
    currency = "RSD"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/",
            callback=self.parse_home,
            headers=_HEADERS,
            meta={"impersonate": "chrome124"},
        )

    def parse_home(self, response):
        yield scrapy.Request(
            f"{_BASE}/session/init",
            callback=self.parse_init,
            headers=_HEADERS,
            meta={"impersonate": "chrome124"},
        )

    def parse_init(self, response):
        yield scrapy.Request(
            f"{_BASE}/v2/categories",
            callback=self.parse_categories,
            headers=_HEADERS,
            meta={"impersonate": "chrome124"},
        )

    def parse_categories(self, response):
        tree = response.json()
        cat_ids: list[int] = []
        _collect_category_ids(tree, cat_ids)
        logger.info(f"idea_rs: {len(cat_ids)} categories with products")

        for cid in cat_ids:
            yield scrapy.Request(
                f"{_BASE}/v2/categories/{cid}/products?page=1",
                callback=self.parse_products,
                headers=_HEADERS,
                meta={"impersonate": "chrome124", "category_id": cid, "page": 1},
            )

    def parse_products(self, response):
        cid = response.meta["category_id"]
        page = response.meta["page"]

        data = response.json()
        products = data.get("products") or []
        page_info = data.get("_page") or {}
        page_count = page_info.get("page_count", page)

        scraped_at = datetime.now(timezone.utc).isoformat()
        n_yielded = 0
        for p in products:
            pid = p.get("id")
            name = p.get("name")
            price_obj = (p.get("price") or {}).get("amount")
            if pid is None or not name or price_obj is None:
                continue
            try:
                price_val = float(price_obj) / 100.0
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue

            name = re.sub(r"\s+", " ", str(name)).strip()
            categories = p.get("categories") or []
            category = categories[0]["name"] if categories else None

            n_yielded += 1
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": category,
                "price": str(price_val),
                "currency": self.currency,
                "url": f"{_BASE}{p.get('product_path', '')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"idea_rs: category={cid} page={page}/{page_count} yielded={n_yielded}"
        )

        if page < page_count:
            yield scrapy.Request(
                f"{_BASE}/v2/categories/{cid}/products?page={page + 1}",
                callback=self.parse_products,
                headers=_HEADERS,
                meta={
                    "impersonate": "chrome124",
                    "category_id": cid,
                    "page": page + 1,
                },
            )
