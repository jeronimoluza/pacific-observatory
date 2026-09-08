"""Ori Nabiji ("2 Nabiji") -- https://2nabiji.ge/ (Tbilisi, Georgia).

"Ori Nabiji" is a Georgian supermarket chain; ``2nabiji.ge`` is its online
store ("order the full 2 Nabiji assortment at the same price as in store").
The storefront is a Next.js SPA whose catalog sits behind an open,
unauthenticated JSON API on ``catalog-api.orinabiji.ge``. A prior Georgia
pass stopped at "same Next.js SPA-shell signature as bigmarket.ge, not probed
further" -- a Playwright network trace on a *category* page (not the
homepage) surfaces the two calls this spider uses.

Flow:

1. ``GET /catalog/api/categories/thin?lang=ge`` -> 238 category documents,
   each with ``_id``, ``parent`` (absent on the 14 roots) and ``name.ge``.
   Leaves are the 190 ids that never appear as another node's ``parent``.
2. ``POST /catalog/api/products/search?lang=ge&sortField=isInStock&
   sortDirection=-1`` with body ``{"skip": N, "limit": 50,
   "categoryIds": ["<leaf id>"]}`` -> ``data.products`` +
   ``data.totalCount``. Querying one leaf at a time (rather than the whole
   subtree the site itself sends) keeps each product on exactly one shelf.

Price: the API returns a base price at ``stock.price`` and, when a promotion
is live, an effective price at ``discount.price``. This spider emits the
**effective** price (``discount.price`` when present and > 0, else
``stock.price``) so rows match what the shopper is charged, and records the
base price only implicitly. Values are plain GEL decimals, not minor units
(verified against the rendered PDP: "ღვინო თეთრი თელიანი ველი 0,75ლ",
stock.price 10.95, discount.price 7.99).

``/ge/product/<nameSlug>`` IS a genuine server-rendered route
(``page: "/[lang]/product/[product-slug]"``, og:title carries the real
product title, and a bogus slug returns HTTP 404) -- so ``url`` is a real
permalink here, unlike the sibling ``agrohub_ge``.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CAT_URL = "https://catalog-api.orinabiji.ge/catalog/api/categories/thin?lang=ge"
_SEARCH_URL = (
    "https://catalog-api.orinabiji.ge/catalog/api/products/search"
    "?lang=ge&sortField=isInStock&sortDirection=-1"
)
_PAGE_SIZE = 50
_MAX_PAGES = 60


class OrinabijiGeSpider(scrapy.Spider):
    name = "orinabiji_ge"
    allowed_domains = ["catalog-api.orinabiji.ge"]
    currency = "GEL"
    language = "ka"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

    async def start(self):
        yield scrapy.Request(
            _CAT_URL, callback=self.parse_categories, headers=self.HEADERS,
            errback=self.errback,
        )

    def parse_categories(self, response):
        try:
            cats = json.loads(response.text).get("data") or []
        except json.JSONDecodeError:
            logger.error("%s: non-JSON category payload", self.name)
            return

        by_id = {c["_id"]: c for c in cats if c.get("_id")}
        parents = {c.get("parent") for c in cats if c.get("parent")}
        leaves = [c for c in cats if c["_id"] not in parents]
        logger.info("%s: %d categories, %d leaves", self.name, len(cats), len(leaves))

        for leaf in leaves:
            path = self._path(leaf, by_id)
            yield self._search_request(leaf["_id"], path, 0)

    @staticmethod
    def _path(node, by_id):
        names, seen = [], set()
        cur = node
        while cur is not None and cur.get("_id") not in seen:
            seen.add(cur.get("_id"))
            nm = (cur.get("name") or {}).get("ge") or ""
            if nm:
                names.append(nm.strip())
            cur = by_id.get(cur.get("parent"))
        return " > ".join(reversed(names))

    def _search_request(self, cat_id, path, skip):
        body = {"skip": skip, "limit": _PAGE_SIZE, "categoryIds": [cat_id]}
        return scrapy.Request(
            _SEARCH_URL,
            method="POST",
            body=json.dumps(body),
            headers=self.HEADERS,
            callback=self.parse_products,
            meta={"cat_id": cat_id, "cat_path": path, "skip": skip},
            dont_filter=True,
            errback=self.errback,
        )

    def parse_products(self, response):
        cat_id = response.meta["cat_id"]
        path = response.meta["cat_path"]
        skip = response.meta["skip"]
        try:
            data = json.loads(response.text).get("data") or {}
        except json.JSONDecodeError:
            logger.error("%s: non-JSON search response for %s", self.name, cat_id)
            return

        products = data.get("products") or []
        if not products:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for raw in products:
            item = self._item(raw, path, scraped_at)
            if item:
                yield item

        total = data.get("totalCount") or 0
        nxt = skip + _PAGE_SIZE
        if nxt < total and nxt < _MAX_PAGES * _PAGE_SIZE:
            yield self._search_request(cat_id, path, nxt)

    def _item(self, raw: dict, cat_path: str, scraped_at: str):
        name = (raw.get("title") or "").strip()
        if not name:
            return None
        stock = raw.get("stock") or {}
        base = stock.get("price")
        disc = (raw.get("discount") or {}).get("price")
        price = disc if disc not in (None, 0, "0") else base
        try:
            amount = float(price)
        except (TypeError, ValueError):
            return None
        if amount <= 0:
            return None
        pid = raw.get("barCode") or raw.get("productId") or raw.get("_id")
        slug = raw.get("nameSlug")
        url = (
            f"https://2nabiji.ge/ge/product/{slug}"
            if slug
            else "https://2nabiji.ge/ge"
        )
        return {
            "product_id": str(pid) if pid else None,
            "product_name": name,
            "category": cat_path or None,
            "price": f"{amount:.2f}",
            "currency": self.currency,
            "available": bool(raw.get("isInStock", True)),
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(
            "%s: request failed %s — %r", self.name, failure.request.url, failure.value
        )
