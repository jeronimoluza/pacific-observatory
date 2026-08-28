"""
Spider for Dismac (Bolivia) -- https://www.dismac.com.bo/.

Electronics/appliances retailer, Magento 2 storefront. The shard flagged
this TIER_1A_HTML because /rest/V1/products 401s, but re-probing live found
/graphql open and unauthenticated (confirmed via storeConfig and
categoryList queries returning real data). Root category id=3 ("Categorías")
carries the full 6,315-product catalog directly (its children -- Línea
Blanca, Tecnología, Hogar y muebles, etc. -- are a real taxonomy but sum to
less than the root due to cross-listing), so this walks the root id
directly rather than the child categories, same pattern as farmashop_uy.
Verified live 2026-08-17: root-category products query returns real BOB
prices (e.g. "Parlante JVC Speaker XL LED 230W" at 3699 BOB). A small
minority (16/6315 on a full run) are 0-priced "Garantía extendida ..."
warranty add-on line items rather than real products; `_item` drops those.
"""

import json

import scrapy

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider

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
# field mixes real taxonomy nodes with marketing/promo collections. Verified
# live against the actual category trees these products carry (e.g. a Karcher
# steam-cleaner nozzle also tags "¡Exclusivos Online!" and "Marcas" -- both
# shallow, non-taxonomic collections that outrank the real "Electrohogar" /
# "Aspiradoras e hidrolavadoras" chain if picked by shallowest-level).
_STOP_NAME_EXACT = {
    "categorías",
    "categorias",
    "home",
    "default category",
    "¡exclusivos online!",
    "marcas",
}
_STOP_NAME_SUBSTR = (
    "oferta",
    "promocion",
    "novedades",
    "hot sale",
    "aniversario",
    "marketplace",
    "mundial",
    "somos #1",
    "operación invierno",
    "operacion invierno",
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
    # Deepest node wins, not shallowest: Magento's marketing/campaign
    # collections sit at level 2 alongside the real taxonomy root, while the
    # genuine department/subcategory chain runs deeper -- picking max(level)
    # favors the specific real category over a shallow campaign bucket that
    # slipped past the name filter.
    best = max(pool, key=lambda c: (c.get("level") or 0, len(c.get("url_path") or "")))
    return best.get("name")


class DismacBoSpider(MagentoGraphQLBaseSpider):
    name = "dismac_bo"
    allowed_domains = ["dismac.com.bo"]
    currency = "BOB"
    language = "es"

    GRAPHQL_URL = "https://www.dismac.com.bo/graphql"
    BASE_URL = "https://www.dismac.com.bo"
    ROOT_CATEGORY_ID = "3"
    WALK_ROOT_DIRECTLY = True
    PAGE_SIZE = 100
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

    def _item(self, p: dict):
        item = super()._item(p)
        if not item:
            return None
        if float(item["price"]) <= 0:
            return None
        item["category"] = _pick_category(p.get("categories") or [])
        return item
