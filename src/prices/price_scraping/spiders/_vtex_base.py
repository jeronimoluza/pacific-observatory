"""
Shared base class for VTEX-platform spiders (Cencosud, Walmart Centroamerica,
and independent VTEX tenants across LAC).

VTEX's catalog_system product-search endpoint caps out around `_from=2500`
overall, so a whole-catalog crawl must partition by category rather than
walk the flat endpoint. We fetch `/api/catalog_system/pub/category/tree/3`,
flatten it to its leaf-most nodes (nodes whose `children` list is empty --
either a true leaf or a depth-3 cutoff node), and page each leaf's full
root-to-leaf id path (`fq=C:/<id>/<id>/.../`) in windows of 50
(`_to - _from` must be <= 49; larger windows return HTTP 400). Querying a
category by its full id path returns products from that category AND all
its descendants (verified live via the `resources: from-to/total` response
header on a parent vs. child category), so leaf-only crawling is both
disjoint and complete without re-walking every tree level.

An offer whose default seller reports `AvailableQuantity: 0` is skipped
outright: VTEX keeps a delisted SKU in the catalog feed forever and leaves
`commertialOffer.Price` frozen at whatever it was when the SKU went out of
stock. The Cencosud AR banners (disco/jumbo/vea) serve ~95% of their feed
that way, so 36% of their rows were pre-devaluation prices -- 35.55 ARS for
a bag of icing sugar, unchanged across a month of weekly runs (0.3% of those
rows moved, vs. 11% of in-stock rows). Absent AvailableQuantity is not zero
and is still emitted.

Subclasses set: name, allowed_domains, HOST, currency, language.
Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
MAX_PAGES_PER_CATEGORY = 60  # safety cap: 60 * 50 = 3000 items/leaf category

# Archived storefront product-detail pages (not the catalog_system API) embed
# the page's Apollo-normalized GraphQL cache as a flat dict in a __STATE__
# <template>/<script> tag -- product entries keyed "Product:<slug>", SKUs
# under "<slug>.items.<n>", offers under "...sellers.<n>.commertialOffer".
# Older/legacy (non-IO) VTEX themes may lack it; JSON-LD is the fallback.
_STATE_RE = re.compile(
    r'data-varname="__STATE__">\s*<script[^>]*>(\{.*?\})</script>', re.DOTALL
)
_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)


def _resolve_ref(state, ref):
    """Follow one Apollo-cache reference: {"type": "id", "id": ...} or {"type": "json", ...}."""
    if isinstance(ref, dict) and ref.get("type") == "id" and "id" in ref:
        return state.get(ref["id"])
    if isinstance(ref, dict) and ref.get("type") == "json":
        return ref.get("json")
    return ref


class VtexBaseSpider(scrapy.Spider):
    name = None
    HOST: str = ""

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
        self.seen_skus = set()
        yield scrapy.Request(
            f"https://{self.HOST}/api/catalog_system/pub/category/tree/3",
            callback=self.parse_tree,
        )

    def parse_tree(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON category tree at {response.url}")
            return
        leaves = []
        self._collect_leaves(tree, [], leaves)
        logger.info(f"{self.name}: {len(leaves)} leaf categories")
        for path, cat_name in leaves:
            yield self._page_request(path, cat_name, 0)

    def _collect_leaves(self, nodes, path, leaves):
        for node in nodes or []:
            node_path = path + [str(node.get("id"))]
            children = node.get("children") or []
            if children:
                self._collect_leaves(children, node_path, leaves)
            else:
                leaves.append((node_path, node.get("name")))

    def _page_request(self, path, cat_name, from_):
        to_ = from_ + PAGE_SIZE - 1
        fq = "/".join(path)
        url = (
            f"https://{self.HOST}/api/catalog_system/pub/products/search"
            f"?fq=C:/{fq}/&_from={from_}&_to={to_}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"path": path, "cat_name": cat_name, "from_": from_},
            dont_filter=True,
        )

    def parse_page(self, response):
        if response.status not in (200, 206):
            return
        try:
            products = response.json()
        except ValueError:
            return
        if not isinstance(products, list) or not products:
            return
        path = response.meta["path"]
        cat_name = response.meta["cat_name"]
        from_ = response.meta["from_"]
        for p in products:
            for item in self._items(p, cat_name):
                yield item
        page_num = from_ // PAGE_SIZE
        if len(products) >= PAGE_SIZE and page_num + 1 < MAX_PAGES_PER_CATEGORY:
            yield self._page_request(path, cat_name, from_ + PAGE_SIZE)

    def _items(self, p: dict, cat_name):
        categories = p.get("categories") or []
        category = (
            categories[0].strip("/").replace("/", " > ") if categories else cat_name
        )
        link_text = p.get("linkText")
        url = (
            f"https://{self.HOST}/{link_text}/p" if link_text else (p.get("link") or "")
        )
        product_name = str(p.get("productName") or "").strip()[:500]
        for it in p.get("items") or []:
            sku_id = it.get("itemId")
            if not sku_id or sku_id in self.seen_skus:
                continue
            sellers = it.get("sellers") or []
            if not sellers:
                continue
            seller = next((s for s in sellers if s.get("sellerDefault")), sellers[0])
            offer = seller.get("commertialOffer") or {}
            price = offer.get("Price")
            available_qty = offer.get("AvailableQuantity")
            if available_qty == 0 or price is None:
                continue
            self.seen_skus.add(sku_id)
            yield {
                "product_id": str(sku_id),
                "product_name": product_name,
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(available_qty) if available_qty is not None else True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    @classmethod
    def parse_html(cls, html, url):
        """Parse one archived VTEX product-detail page into per-SKU price rows.

        Pure and stateless (no Scrapy Response, no network, no `self.seen_skus` --
        that dedup set only exists on a live crawl instance). Tries the Apollo
        `__STATE__` cache first since it maps directly onto the same fields
        `_items()` reads from the catalog_system API; falls back to the page's
        JSON-LD `Product` block when `__STATE__` is missing or unparsable.
        Yields nothing for a non-product page. Does not stamp `scraped_at_utc` --
        the wayback backfiller sets that from the snapshot timestamp.
        """
        state = cls._parse_state_blob(html)
        if state is not None:
            rows = list(cls._rows_from_state(state))
            if rows:
                return rows
        return list(cls._rows_from_jsonld(html, url))

    @staticmethod
    def _parse_state_blob(html):
        m = _STATE_RE.search(html)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except (ValueError, TypeError):
            return None

    @classmethod
    def _rows_from_state(cls, state):
        # A product-detail page's __STATE__ has exactly one top-level
        # "Product:<slug>" key (no "." in it -- nested keys are its SKUs/specs).
        for key, prod in state.items():
            if (
                not key.startswith("Product:")
                or "." in key
                or not isinstance(prod, dict)
            ):
                continue
            yield from cls._product_rows(state, prod)

    @classmethod
    def _product_rows(cls, state, prod):
        categories = _resolve_ref(state, prod.get("categories")) or []
        category = categories[0].strip("/").replace("/", " > ") if categories else None
        product_name = str(prod.get("productName") or "").strip()[:500]
        link_text = prod.get("linkText")
        page_url = (
            f"https://{cls.HOST}/{link_text}/p"
            if link_text
            else (prod.get("link") or "")
        )

        for item_ref in prod.get("items") or []:
            item = _resolve_ref(state, item_ref)
            if not isinstance(item, dict):
                continue
            sku_id = item.get("itemId")
            if not sku_id:
                continue
            sellers = [_resolve_ref(state, s) for s in item.get("sellers") or []]
            sellers = [s for s in sellers if isinstance(s, dict)]
            if not sellers:
                continue
            seller = next((s for s in sellers if s.get("sellerDefault")), sellers[0])
            offer = _resolve_ref(state, seller.get("commertialOffer"))
            if not isinstance(offer, dict):
                continue
            price = offer.get("Price")
            available_qty = offer.get("AvailableQuantity")
            if available_qty == 0 or price is None:
                continue
            yield {
                "product_id": str(sku_id),
                "product_name": product_name,
                "category": category,
                "price": str(price),
                "currency": cls.currency,
                "available": bool(available_qty) if available_qty is not None else True,
                "url": page_url,
                "language": cls.language,
            }

    @classmethod
    def _rows_from_jsonld(cls, html, url):
        for m in _JSONLD_RE.finditer(html):
            try:
                data = json.loads(m.group(1))
            except (ValueError, TypeError):
                continue
            for obj in data if isinstance(data, list) else [data]:
                if not isinstance(obj, dict) or obj.get("@type") != "Product":
                    continue
                yield from cls._jsonld_product_rows(obj, url)

    @classmethod
    def _jsonld_product_rows(cls, obj, url):
        product_name = str(obj.get("name") or "").strip()[:500]
        offers = obj.get("offers") or {}
        offer_list = offers.get("offers") if isinstance(offers, dict) else None
        if (
            not offer_list
            and isinstance(offers, dict)
            and offers.get("@type") == "Offer"
        ):
            offer_list = [offers]
        for off in offer_list or []:
            if not isinstance(off, dict) or off.get("price") is None:
                continue
            sku_id = off.get("sku") or obj.get("sku") or obj.get("mpn")
            available = "instock" in str(off.get("availability") or "").lower()
            yield {
                "product_id": str(sku_id) if sku_id else None,
                "product_name": product_name,
                "category": None,
                "price": str(off.get("price")),
                "currency": off.get("priceCurrency") or cls.currency,
                "available": available,
                "url": obj.get("@id") or url,
                "language": cls.language,
            }
