"""
Spider for GO.cv (Cabo Verde) -- https://www.go.cv/.

National postal-service (Correios de Cabo Verde) marketplace, multi-vendor,
prices in CVE. Next.js storefront over a Vendure commerce backend at
api.go.cv -- confirmed live via Playwright network trace 2026-09-06
(`GET https://api.go.cv/shop-api?languageCode=pt`, no auth/session needed).

Category tree is served whole by the frontend's own proxy route:
  GET https://www.go.cv/api/site-categories?locale=pt
      -> nested {"id","name","slug","children":[...]} tree, 423 category
      slugs total once flattened (root + descendants).

Product search is a standard Vendure GraphQL `search` query against
api.go.cv/shop-api, keyed by `collectionSlug` (the category slug), with
working `skip`/`take` pagination (confirmed: `bebidas` returns totalItems=5
and exactly 5 items for take=100):

  POST https://api.go.cv/shop-api?languageCode=pt
  { "query": "query Search($input: SearchInput!) { search(input: $input)
      { totalItems items { productId productName slug priceWithTax
      { ... on SinglePrice { value } } currencyCode } } }",
    "variables": {"input": {"collectionSlug": "<slug>", "take": 100,
                             "skip": <n>}} }

CURRENCY-PRECISION GOTCHA: Vendure's shop-api commonly returns prices in
thousandths on other channels (see rohlik-family / KoRo notes elsewhere in
this repo), but THIS channel is configured in ordinary cents -- confirmed
live 2026-09-06 by cross-checking the API's raw value (25000) for
"Biscoitos da Avó Mila" against the rendered PDP at
https://www.go.cv/product/aa00-biscoitos-da-avo-mila, which displays
"250.00 CVE". Divide by 100, NOT 1000, for this source. Do not copy the
KoRo/Rohlik divisor here without re-checking -- it is channel-configured,
not a Vendure-wide constant.

Category tree is hierarchical and heavily nested (13 root departments x
many levels of children); the same product can appear under more than one
collectionSlug (a parent collection typically includes its children's
products), so results are deduped by productId across the whole crawl.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITE_CATEGORIES_URL = "https://www.go.cv/api/site-categories?locale=pt"
_SHOP_API_URL = "https://api.go.cv/shop-api?languageCode=pt"
_PAGE_SIZE = 100

_SEARCH_QUERY = """
query Search($input: SearchInput!) {
  search(input: $input) {
    totalItems
    items {
      productId
      productName
      slug
      priceWithTax {
        ... on SinglePrice { value }
        ... on PriceRange { min max }
      }
      currencyCode
    }
  }
}
"""


def _flatten_slugs(categories, out):
    for cat in categories or []:
        slug = cat.get("slug")
        if slug:
            out.append(slug)
        _flatten_slugs(cat.get("children") or [], out)


class GoCvSpider(scrapy.Spider):
    name = "go_cv"
    allowed_domains = ["go.cv", "api.go.cv"]
    currency = "CVE"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.go.cv/"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    async def start(self):
        yield scrapy.Request(_SITE_CATEGORIES_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        slugs = []
        _flatten_slugs(data.get("categories") or [], slugs)
        slugs = sorted(set(slugs))
        logger.info(f"go_cv: {len(slugs)} category slugs")
        for slug in slugs:
            yield self._search_request(slug, skip=0)

    def _search_request(self, slug, skip):
        body = {
            "query": _SEARCH_QUERY,
            "variables": {
                "input": {"collectionSlug": slug, "take": _PAGE_SIZE, "skip": skip}
            },
        }
        return scrapy.Request(
            _SHOP_API_URL,
            method="POST",
            body=json.dumps(body),
            headers={"Content-Type": "application/json"},
            callback=self.parse_search,
            meta={"slug": slug, "skip": skip},
        )

    def parse_search(self, response):
        slug = response.meta["slug"]
        skip = response.meta["skip"]
        try:
            data = response.json()
        except ValueError:
            return
        result = (data.get("data") or {}).get("search") or {}
        items = result.get("items") or []
        total = result.get("totalItems", 0)
        logger.info(f"go_cv: slug={slug} skip={skip} items={len(items)} total={total}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            pid = item.get("productId")
            if not pid or pid in self._seen_ids:
                continue
            price_obj = item.get("priceWithTax") or {}
            raw = price_obj.get("value")
            if raw is None:
                raw = price_obj.get("min")
            if raw is None:
                continue
            price = raw / 100.0
            if price <= 0:
                continue
            self._seen_ids.add(pid)
            yield {
                "product_id": pid,
                "product_name": (item.get("productName") or "").strip()[:500],
                "category": slug,
                "price": price,
                "currency": item.get("currencyCode", self.currency),
                "available": True,
                "url": f"https://www.go.cv/product/{item.get('slug', '')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if skip + _PAGE_SIZE < total:
            yield self._search_request(slug, skip + _PAGE_SIZE)
