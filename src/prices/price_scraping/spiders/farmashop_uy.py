"""Farmashop (Uruguay) -- https://tienda.farmashop.com.uy/. Pharmacy chain, Magento 2 storefront.
The REST endpoint (/rest/V1/products) 401s unauthenticated; the GraphQL endpoint is open. Root
category id=2 returns ~19.5k products directly (close to the sum of its department children, which
overlap on cross-cutting marketing categories like Promociones/Ofertas/Outlet), so the spider walks
the root id directly rather than categoryList children."""

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

# Magento's `categories` field returns every category node a product is
# assigned to, mixing real taxonomy with cross-cutting marketing/promo
# collections (Ofertas, Mailing, Black Friday, brand rollups...). Filter
# those out by name, then pick the shallowest remaining node as the
# best-effort single category label.
_STOP_NAME_EXACT = {"marcas", "categorías", "categorias", "home", "default category"}
_STOP_NAME_SUBSTR = (
    "oferta",
    "black friday",
    "black-friday",
    "mailing",
    "campañ",
    "campan",
    "verano",
    "día del",
    "dia del",
    "más vendido",
    "mas vendido",
    "novedades",
    "exclusiv",
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
    best = min(pool, key=lambda c: (c.get("level") or 99, len(c.get("url_path") or "")))
    return best.get("name")


class FarmashopUySpider(MagentoGraphQLBaseSpider):
    name = "farmashop_uy"
    allowed_domains = ["farmashop.com.uy"]
    currency = "UYU"
    language = "es"

    GRAPHQL_URL = "https://tienda.farmashop.com.uy/graphql"
    BASE_URL = "https://tienda.farmashop.com.uy"
    ROOT_CATEGORY_ID = "2"
    WALK_ROOT_DIRECTLY = True

    def _page_request(self, category_id: str, page: int):
        # Root-level query in _magento_base doesn't request `categories`;
        # override with the same query plus that field so category isn't null.
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
        if item:
            item["category"] = _pick_category(p.get("categories") or [])
        return item
