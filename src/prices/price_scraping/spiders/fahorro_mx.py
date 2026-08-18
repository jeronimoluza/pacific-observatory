"""
Spider for Farmacias del Ahorro (Mexico) -- https://www.fahorro.com/.

Large Mexican pharmacy chain, Magento 2 storefront. The shard's evidence
was SSR-HTML with Incapsula cookies present but not blocking; re-probing
live found /rest/V1/products WAF-blocked (403 Incapsula "Forbidden_VCL")
but /graphql open and unauthenticated (storeConfig and categoryList both
return real data, store_code "mx"). Root category id=2 carries the whole
68,009-product catalog directly (its children are a mix of departments --
Farmacia, Electrónica, Hogar, Belleza, Deportes, etc. -- and marketing
collections that overlap heavily, e.g. "Catálogo Extendido" alone is
10,626), so this walks the root id directly. A meaningful slice of the
root-level catalog carries a `0` placeholder price (verified live: 5/5 of
the first root page were price=0, while a real department like Farmacia
(id=7404) is clean) -- `_item` drops those rather than shipping zero-price
rows. Verified live 2026-08-17: Farmacia products return real MXN prices
(e.g. "Meloxicam 15 mg 10 Caps Marca del Ahorro" at 105 MXN).

`categories` comes back genuinely empty for every product when queried at
this root scope (confirmed live: 0/30 nonempty on a spot page, vs. the same
field populating fine when queried from a leaf department id like 7404) --
a Magento GraphQL quirk on this install's root/"Default Category" node, not
a bug in `_pick_category`. Getting real category labels would need a
per-department walk instead of the root, which reintroduces the
cross-listing duplication this file avoids by walking root directly, so
`category` ships as None here (same as homecenter_co.py).

A first full run under-collected (278 rows off 17 requests, `finish_reason:
finished`) because _magento_base's stock `parse_page` stops paginating the
first time a page returns fewer than PAGE_SIZE items -- and this catalog
serves short-but-not-final pages mid-walk (confirmed live: page 17 of the
root walk returned 199/200 items while pages 18 and 20 still returned full
200-item pages). `parse_page` is overridden here to continue off the API's
own `total_count` instead, matching sodimac_pe's count-based pagination.
"""

import json
import logging

import scrapy

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider

logger = logging.getLogger(__name__)

_PRODUCTS_QUERY_WITH_CATEGORY = """
{ products(filter: {category_id: {eq: "%s"}}, pageSize: %d, currentPage: %d) {
    total_count
    items {
      sku
      name
      url_key
      categories { name level url_path }
      price_range { minimum_price { final_price { value currency } } }
    }
  }
}
"""

# Same cross-cutting-collection filter as farmashop_uy: Magento's `categories`
# field mixes real departments with marketing/promo/landing collections.
_STOP_NAME_EXACT = {
    "home",
    "default category",
    "catálogo extendido",
    "landings",
    "campañas",
}
_STOP_NAME_SUBSTR = (
    "liquidacion",
    "fashion days",
    "back to school",
    "campañ",
    "verano saludable",
    "trade",
)


def _pick_category(categories: list[dict]) -> str | None:
    if not categories:
        return None
    candidates = [
        c
        for c in categories
        if c.get("name")
        and c["name"].strip().lower() not in _STOP_NAME_EXACT
        and not any(s in c["name"].strip().lower() for s in _STOP_NAME_SUBSTR)
    ]
    pool = candidates or categories
    # Deepest node wins, not shallowest: the shallow department roots
    # (Farmacia, Diabetes, ...) sit at the same level as marketing
    # collections, while the genuine subcategory chain runs deeper --
    # verified live (e.g. "Beniflant Spray" tags Farmacia(2) > Salud
    # Respiratoria(3) > Dolor de Garganta(4); max(level) picks the specific
    # "Dolor de Garganta" over the generic "Farmacia").
    best = max(pool, key=lambda c: (c.get("level") or 0, len(c.get("url_path") or "")))
    return best.get("name")


class FahorroMxSpider(MagentoGraphQLBaseSpider):
    name = "fahorro_mx"
    allowed_domains = ["fahorro.com"]
    currency = "MXN"
    language = "es"

    GRAPHQL_URL = "https://www.fahorro.com/graphql"
    BASE_URL = "https://www.fahorro.com"
    ROOT_CATEGORY_ID = "2"
    WALK_ROOT_DIRECTLY = True
    PAGE_SIZE = 200
    MAX_PAGES = 400

    def _page_request(self, category_id: str, page: int):
        return scrapy.Request(
            self.GRAPHQL_URL,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "query": _PRODUCTS_QUERY_WITH_CATEGORY
                    % (category_id, self.PAGE_SIZE, page)
                }
            ),
            callback=self.parse_page,
            meta={"category_id": category_id, "page": page},
        )

    def parse_page(self, response):
        # Override _magento_base's continuation check: it stops as soon as
        # one page returns fewer than PAGE_SIZE items, but this catalog
        # returns short pages (e.g. 199/200) mid-walk that aren't actually
        # the end -- confirmed live 2026-08-17 (page 17 of the root walk
        # returned 199 items, yet pages 18/20 still returned full 200-item
        # pages). Use the API's own `total_count` instead, same as
        # sodimac_pe's count-based pagination.
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        block = (data.get("data") or {}).get("products") or {}
        items = block.get("items") or []
        total_count = block.get("total_count") or 0
        category_id = response.meta["category_id"]
        page = response.meta["page"]
        logger.info(
            f"{self.name}: page={page} count={len(items)} total_count={total_count}"
        )
        for p in items:
            item = self._item(p)
            if item:
                yield item
        if page * self.PAGE_SIZE < total_count and page < self.MAX_PAGES:
            yield self._page_request(category_id, page + 1)

    def _item(self, p: dict):
        item = super()._item(p)
        if not item:
            return None
        if float(item["price"]) <= 0:
            return None
        item["category"] = _pick_category(p.get("categories") or [])
        return item
