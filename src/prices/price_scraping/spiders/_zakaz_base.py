"""Shared base class for Ukrainian retailers running on the Zakaz.ua platform.

Zakaz.ua (Zakaz LLC, Kyiv) is a white-label e-grocery platform: each partner
retail chain gets its own storefront subdomain (``novus.zakaz.ua``,
``metro.zakaz.ua``, ``auchan.zakaz.ua``, ...) but every one of them is served
by a single, completely open, unauthenticated JSON API at
``https://stores-api.zakaz.ua``.

Discovery note (2026-09-05): ``https://zakaz.ua/`` itself returns HTTP 403
under ``curl_cffi impersonate=chrome124`` — that is what the pre-existing
``known_blockers.md`` entry recorded. **The block is on the marketing root
only.** The per-chain storefront subdomains AND the API host answer 200 with
no headers, no cookies and no TLS impersonation at all (verified: a bare
``requests``-style GET with no ``Origin``/``Referer`` returns the full
payload). The old verdict was a false negative for the platform as a whole.

API shape (all GET, all anonymous):

1. ``/stores/`` -> 67 store objects, each with ``id``, ``retail_chain``,
   ``city``, ``currency``. Chains are physically separate companies (Novus,
   Auchan, METRO, Megamarket, Tavria V, Eko-market, WineTime, ...) that each
   price independently — one source per chain, one pinned ``store_id`` each.
2. ``/stores/<store_id>/categories/`` -> the chain's full category tree
   (nested ``children``); leaves carry a slug ``id`` and a ``count``.
3. ``/stores/<store_id>/categories/<cat_id>/products/?page=N`` -> 30 products
   per page, ``count`` = total for the category. Pagination terminates
   cleanly: the first page past the end returns ``results: []`` (verified on
   ``vegan-foods-novus``: pages 1-16 full/partial, page 17+ empty).

**Price is in minor units (kopiyky) — divide by 100.** ``price: 8399`` is
83.99 UAH, cross-checked against the rendered PDP.

The catalog is store-pinned: prices come from the ``store_id`` this spider
declares, so each subclass pins one real, serviceable store (Kyiv by
convention, matching ``atb_market_ua``/``silpo_ua``, except where a chain has
no Kyiv store).

``web_url`` is canonical *within one storefront*, so the DuplicationPipeline's
url-dedup collapses the platform's heavy cross-listing (promo shelves such as
"Низькоціни" / "1+1" re-list products that also sit in their real department)
instead of emitting it as duplicate rows.

**It is NOT store-independent across banners** (measured 2026-09-06): the same
EAN carries a different ``web_url`` per storefront —
``megamarket.zakaz.ua/uk/products/<slug>--<ean>/`` vs
``ultramarket.zakaz.ua/uk/products/<slug>--<ean>/``. url-dedup therefore does
NOT collapse banner twins, which is why multi-store subclasses dedup on
``ean``/``sku`` explicitly (see ``STORES`` below).

Multi-store mode: a subclass that sets ``STORES`` (an ordered
``{store_id: storefront}`` map) crawls every listed store under one source name
and emits each product exactly once, first store wins. This is for banner
GROUPS — several storefronts of one operator at shared addresses that quote
identical prices — where treating each banner as an independent source would
inflate ``n_obs`` and drag the published median. Independent chains keep one
store each via ``STORE_ID``/``STOREFRONT``.

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


def _strip_store_prefix(value) -> str:
    """Normalise a Zakaz identifier to its digits.

    ``kharkiv00000002335310`` -> ``00000002335310``; a genuine all-digit EAN
    is returned unchanged. Returns "" for a missing/non-identifying value.
    """
    text = str(value or "").strip()
    return re.sub(r"^\D+", "", text)


_API = "https://stores-api.zakaz.ua"
_PAGE_SIZE = 30
_MAX_PAGES = 120  # safety cap: 3,600 items per leaf category


class ZakazBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, STORE_ID, STOREFRONT.
    name = None
    allowed_domains = ["stores-api.zakaz.ua"]
    currency = "UAH"
    language = "uk"

    STORE_ID: str = ""
    STOREFRONT: str = ""  # e.g. "novus.zakaz.ua" — used for Referer only
    # Optional ordered {store_id: storefront} for banner groups. When set it
    # supersedes STORE_ID/STOREFRONT and products are deduped on ean/sku
    # across every listed store, first store wins.
    STORES: dict[str, str] = {}

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def _stores(self) -> dict[str, str]:
        """Ordered {store_id: storefront}. Single-store subclasses get one entry."""
        return dict(self.STORES) if self.STORES else {self.STORE_ID: self.STOREFRONT}

    def _headers(self, storefront: str | None = None):
        return {
            "Accept": "application/json",
            "Accept-Language": "uk",
            "Referer": f"https://{storefront or self.STOREFRONT}/",
        }

    async def start(self):
        # Cross-store dedup only in banner-group mode. Single-store subclasses
        # keep their previous behaviour exactly (url-dedup in the pipeline).
        self._seen: set[str] | None = set() if self.STORES else None
        self._deduped = 0
        for store_id, storefront in self._stores().items():
            yield scrapy.Request(
                f"{_API}/stores/{store_id}/categories/",
                callback=self.parse_categories,
                headers=self._headers(storefront),
                meta={"store_id": store_id, "storefront": storefront},
                errback=self.errback,
                dont_filter=True,
            )

    # ------------------------------------------------------------------
    def parse_categories(self, response):
        try:
            tree = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: non-JSON category tree", self.name)
            return

        store_id = response.meta.get("store_id", self.STORE_ID)
        storefront = response.meta.get("storefront", self.STOREFRONT)
        leaves = []
        self._walk(tree, [], leaves)
        logger.info("%s: %d leaf categories (%s)", self.name, len(leaves), storefront)
        for cat_id, path in leaves:
            yield self._page_request(cat_id, path, 1, store_id, storefront)

    def _walk(self, nodes, path, out):
        for node in nodes or []:
            title = (node.get("title") or "").strip()
            children = node.get("children") or []
            if children:
                self._walk(children, path + [title], out)
            elif node.get("id"):
                out.append((node["id"], " > ".join([p for p in path + [title] if p])))

    def _page_request(self, cat_id, path, page, store_id=None, storefront=None):
        store_id = store_id or self.STORE_ID
        storefront = storefront or self.STOREFRONT
        return scrapy.Request(
            f"{_API}/stores/{store_id}/categories/{cat_id}/products/?page={page}",
            callback=self.parse_products,
            headers=self._headers(storefront),
            meta={
                "cat_id": cat_id,
                "cat_path": path,
                "page": page,
                "store_id": store_id,
                "storefront": storefront,
            },
            errback=self.errback,
            dont_filter=True,
        )

    def parse_products(self, response):
        cat_id = response.meta["cat_id"]
        path = response.meta["cat_path"]
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: non-JSON products for %s p%d", self.name, cat_id, page)
            return

        results = payload.get("results") or []
        if not results:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for raw in results:
            item = self._item(raw, path, scraped_at)
            if item:
                yield item

        if len(results) >= _PAGE_SIZE and page < _MAX_PAGES:
            yield self._page_request(
                cat_id,
                path,
                page + 1,
                response.meta.get("store_id"),
                response.meta.get("storefront"),
            )

    # ------------------------------------------------------------------
    def _item(self, raw: dict, cat_path: str, scraped_at: str):
        name = (raw.get("title") or "").strip()
        price = raw.get("price")
        if not name or price is None:
            return None
        try:
            amount = float(price) / 100.0  # API returns kopiyky
        except (TypeError, ValueError):
            return None
        if amount <= 0:
            return None
        product_id = raw.get("ean") or raw.get("sku")
        # Banner-group dedup: web_url is per-storefront, so url-dedup cannot
        # collapse the same product listed by two banners of one operator.
        #
        # The identifier fields are not what their names suggest (verified
        # 2026-09-06): for own-label / unbarcoded lines ``ean`` carries a
        # STORE-PREFIXED pseudo-barcode ("kharkiv00000002335310") while
        # ``sku`` carries the bare operator-wide code ("335310"). Deduping on
        # the raw ``ean`` therefore matches nothing across banners. Stripping
        # the leading non-digit prefix normalises both shapes -- a real EAN is
        # already all digits and passes through untouched -- and lifted the
        # Kharkiv pair from 159 to 211 shared keys, 211/211 identically priced.
        dedup_key = _strip_store_prefix(product_id) or f"name:{name.casefold()}"
        seen = getattr(self, "_seen", None)
        if seen is not None:
            if dedup_key in seen:
                self._deduped += 1
                return None
            seen.add(dedup_key)
        url = raw.get("web_url") or f"https://{self.STOREFRONT}/"
        return {
            "product_id": str(product_id) if product_id else None,
            "product_name": name,
            "category": cat_path or None,
            "price": f"{amount:.2f}",
            "currency": (raw.get("currency") or self.currency).upper(),
            "available": bool(raw.get("in_stock", True)),
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def closed(self, reason):
        # Never let banner-group dedup be silent: a run that suppressed
        # nothing is either a genuinely disjoint group or a broken key.
        if self.STORES:
            logger.info(
                "%s: banner-group dedup suppressed %d duplicate products "
                "across %d storefronts (%d kept)",
                self.name,
                getattr(self, "_deduped", 0),
                len(self.STORES),
                len(getattr(self, "_seen", None) or ()),
            )

    def errback(self, failure):
        logger.error(
            "%s: request failed %s — %r", self.name, failure.request.url, failure.value
        )
