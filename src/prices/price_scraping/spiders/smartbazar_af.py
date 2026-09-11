"""
SmartBazar.af (Afghanistan) -- https://smartbazar.af/

A multi-vendor Afghan online marketplace (electronics, home & kitchen,
fashion, foodstuffs, children's items, etc across many independent
shops). Per the onboarding skill's marketplace doctrine, the seller
directory would normally be the target -- but the directory itself is
reachable only through the same GraphQL API this spider already hits,
and building a per-seller crawl was out of scope for this pass. Scraped
here as `channel: marketplace`, scoped to its own "Foodstuffs" category
so the corpus only picks up genuinely food-relevant listings from this
source.

DISCOVERY (Playwright network trace, 2026-09-11): the storefront is a
client-rendered Next.js app; product data is NOT in the server HTML.
Network capture of https://smartbazar.af/en/market?categorySlug=supermarket
showed every listing/category/product call going to a single GraphQL
endpoint, https://api.smartbazar.af/graphql, with NO auth required for
the public* queries (`publicProducts`, `publiCategoriesList`,
`publicShops`).

CATEGORY ID: `publiCategoriesList` returned a real "Foodstuffs" category
(id 665ab3c06a10c23394bd2408, 12 subcategories) distinct from the
"supermarket" URL slug used during discovery (which turned out to be a
much smaller, non-food-only bucket -- laundry powder/soap were the top
two items there). This spider queries the Foodstuffs category id
directly.

ACCESS: plain HTTP POST to https://api.smartbazar.af/graphql with a
`publicProducts` query, `Origin: https://smartbazar.af` header, NO
impersonation/cookies/auth needed -- confirmed working from plain
`requests` on 2026-09-11.

ENUMERABILITY: MEASURED total=85 for the Foodstuffs category id, 20/page,
page1 vs page2 item ids fully disjoint.

CURRENCY: AFN, read directly from each product's own `currency` field in
the GraphQL payload -- not inferred.

coicop_classification: classifier -- product names are short but
specific ("Black garlic", "Coffee", "Mazafati black dates", "Olive oil"),
routed through nameI18n.en; coicop_codes left unset (spans multiple
COICOP-01 classes).
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.smartbazar.af/graphql"
FOODSTUFFS_CATEGORY_ID = "665ab3c06a10c23394bd2408"
PAGE_SIZE = 20
MAX_PAGES = 50

_QUERY = """query PublicProducts($filters: ProductPublicFilterInput, $page: Float, $pageSize: Float) {
  publicProducts(filters: $filters, page: $page, pageSize: $pageSize) {
    page
    pageSize
    total
    items {
      id
      name
      nameI18n
      basePrice
      currency
      categoryId
      subCategoryId
      brand
      slug
      shopId
    }
  }
}"""


class SmartbazarAfSpider(scrapy.Spider):
    name = "smartbazar_af"
    allowed_domains = ["smartbazar.af", "api.smartbazar.af"]
    currency = "AFN"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
    }

    def _payload(self, page: int) -> dict:
        return {
            "operationName": "PublicProducts",
            "variables": {
                "filters": {
                    "categoryId": FOODSTUFFS_CATEGORY_ID,
                    "subCategoryId": None,
                    "maxPrice": None,
                    "minPrice": None,
                    "shopId": None,
                    "province": None,
                    "city": None,
                },
                "page": page,
                "pageSize": PAGE_SIZE,
            },
            "query": _QUERY,
        }

    def start_requests(self):
        yield self._make_request(1)

    def _make_request(self, page: int):
        return scrapy.Request(
            GRAPHQL_URL,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://smartbazar.af",
                "Referer": "https://smartbazar.af/",
            },
            body=json.dumps(self._payload(page)),
            callback=self.parse_page,
            meta={"page": page},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"smartbazar_af: non-JSON response at page {response.meta['page']}")
            return
        block = (data.get("data") or {}).get("publicProducts") or {}
        items = block.get("items") or []
        page = response.meta["page"]
        logger.info(f"smartbazar_af page={page} count={len(items)} total={block.get('total')}")
        for it in items:
            price = it.get("basePrice")
            name_i18n = it.get("nameI18n") or {}
            name = name_i18n.get("en") or it.get("name")
            if not price or not name:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            slug = it.get("slug") or it.get("id")
            yield {
                "product_id": it.get("id"),
                "product_name": str(name).strip()[:500],
                "price": str(price),
                "currency": it.get("currency") or self.currency,
                "category": "Foodstuffs",
                "url": f"https://smartbazar.af/en/products/{slug}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        if items and page < MAX_PAGES:
            yield self._make_request(page + 1)
