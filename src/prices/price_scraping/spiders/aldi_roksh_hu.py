"""
Spider for Aldi Hungary via the ROKSH personal-shopper platform --
https://shop.aldi.hu/ (candidate name in the source list: "Aldi via
ROKSH", https://www.roksh.com/).

Aldi runs no Hungarian online catalogue of its own -- ROKSH is the ONLY
route to Aldi Hungary prices. `shop.aldi.hu` is a ROKSH-hosted, Aldi-
themed storefront (GTM snippet on roksh.com explicitly branches on
`shop.aldi.hu` / `shopalditest.roksh.com`), not the generic multi-retailer
roksh.com comparison landing page -- this spider targets the Aldi-only
storefront directly rather than roksh.com's cross-retailer UI.

ROKSH is an Angular SPA; a Playwright network trace of shop.aldi.hu
(2026-09-06) found the backend at `shopservice.roksh.com`, wide open with
no auth cookie required:

  - `GET /category/GetFullCategoryList?providerCode=ALDI&isOwnWebshop=true`
    -> nested category tree, ~386 leaf nodes (IsLeaf, ProgID slug).
  - `GET /productlist/additionalCategoryProductList?listResultProductNum=1000
    &providerCode=ALDI&isOwnWebshop=true&progIdList=<leaf progID>`
    -> `ProductListResults[0].ProductList[]`, each row nesting
    `productProvider[0]` with `providerProductName`, `price` (HUF),
    `unit`, `available`. Confirmed live: progIdList=friss-tej (fresh milk)
    -> 8 products incl. "MILSANI Laktozmentes ESL tej ... 1 l" HUF 379.00.
    Leaf catalogs are small (single digits to a few dozen), so
    listResultProductNum=1000 always exceeds the true count -- no
    pagination needed.

GOTCHA (per source list): this is a personal-shopper platform, so a
margin on top of Aldi's own shelf price is possible -- record the channel
as `marketplace` accordingly.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_URL = (
    "https://shopservice.roksh.com/category/GetFullCategoryList"
    "?providerCode=ALDI&isOwnWebshop=true"
)
_PRODUCTLIST_URL = (
    "https://shopservice.roksh.com/productlist/additionalCategoryProductList"
    "?listResultProductNum=1000&providerCode=ALDI&isOwnWebshop=true"
    "&progIdList={prog_id}"
)


def _flatten_leaves(nodes: list) -> list:
    leaves = []
    for n in nodes or []:
        children = n.get("ChildList") or []
        if not children:
            prog_id = n.get("ProgID")
            if prog_id:
                leaves.append(prog_id)
        else:
            leaves.extend(_flatten_leaves(children))
    return leaves


class AldiRokshHuSpider(scrapy.Spider):
    name = "aldi_roksh_hu"
    allowed_domains = ["roksh.com", "shop.aldi.hu"]
    currency = "HUF"
    language = "hu"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_CATEGORY_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.warning("aldi_roksh_hu: bad category JSON")
            return
        leaves = _flatten_leaves(tree)
        logger.info("aldi_roksh_hu: %d leaf categories", len(leaves))
        for prog_id in leaves:
            yield scrapy.Request(
                _PRODUCTLIST_URL.format(prog_id=prog_id),
                callback=self.parse_products,
                meta={"prog_id": prog_id},
            )

    def parse_products(self, response):
        try:
            payload = response.json()
        except ValueError:
            return
        for result in payload.get("ProductListResults") or []:
            for row in result.get("ProductList") or []:
                item = self._item(row)
                if item:
                    yield item

    def _item(self, row: dict):
        # `category`, `productName`, `price` live on the ProductList row
        # itself (not nested under productProvider[0], despite that array
        # also carrying a copy of name/price per offering provider).
        name = (row.get("productName") or "").strip()
        product_id = str(row.get("productID") or "")
        price = row.get("price")
        category = (row.get("category") or {}).get("categoryName")
        if not name or not product_id or price in (None, "", 0):
            return None
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(row.get("available", True)),
            "url": f"https://shop.aldi.hu/termek/{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
