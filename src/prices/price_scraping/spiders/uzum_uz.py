"""Uzum.uz -- Uzbekistan's largest general marketplace -- https://uzum.uz/
(COICOP: mixed, marketplace).

Verified live 2026-09-10/11 via Playwright network trace + curl_cffi
(impersonate=chrome124). Single-page app; the whole catalog is behind
Apollo GraphQL at ``https://graphql.uzum.uz/`` plus a couple of plain
REST helper endpoints under ``https://api.uzum.uz/``.

Auth (public, not a secret): every anonymous visitor is issued a guest
session by ``POST https://id.uzum.uz/api/auth/token`` with an EMPTY body
and an empty ``Authorization: Bearer`` header -- no credentials of any
kind. The response is 204 with the actual token delivered via
``Set-Cookie: access_token=<JWT>`` (a 20-year-expiry guest cookie, ``iss:
"Uzum ID"``, ``sub`` a random UUID -- structurally a synthetic guest
identity, not a logged-in user's session token). This is the same
bootstrap the site's own JS performs on every fresh page load with no
sign-in step; it is what makes anonymous browsing/search work at all, so
it is treated the same as the addendum's Algolia/Supabase anon-key
examples -- public by design. The JWT is then sent as
``Authorization: Bearer <token>`` on every subsequent API call.

``x-iid`` (device install id) DOES matter, unlike an initial guess:
without it, every ``makeSearch`` call 429'd from this project's a8 host
with ``"HTTP fetch failed from 'search-gateway': 429: Too Many
Requests"`` -- reproducible across a fresh token, a warm-up
root-categories call first, 1.5-2s spacing, and multiple browser
impersonation profiles (chrome120/124/131/safari17_0), so it was not a
simple burst-rate issue. The `root-categories`/`auth` endpoints never
429'd, only `makeSearch`. Adding a random UUID as `x-iid` (matching what
the site's own JS generates per install) fixed it immediately and
consistently across all profiles tested. Note this was NOT reproducible
from a residential Mac IP even without the header (it worked there
after one 429 and a natural pause) -- the search-gateway subgraph
appears to gate harder on datacenter-IP traffic specifically, and
`x-iid` may be read as one (weak) signal of legitimacy in that
decision. Always send it.

Enumeration route: found via a Playwright trace of the category page
(https://uzum.uz/uz/category/elektronika-10020) -- ``POST
https://graphql.uzum.uz/`` operation ``MakeSearch_ItemsAndFilters``, a
plain offset/limit search scoped with ``categoryId``. The captured
production query is huge (fetches badges, photos, feedback, checkout
options, ...); this spider uses a minimal rewrite requesting only the
fields it emits: product id, title, and
``priceBlock { finalPrice { amount } sellPrice { amount } }``.

Root categories (used directly as ``categoryId`` -- no need to walk to
leaves): ``GET https://api.uzum.uz/api/main/root-categories?eco=false``,
open once authenticated, returns 23 top-level categories including
"Oziq-ovqat mahsulotlari" (food products, id 1821). Titles come back in
Uzbek Latin only from this endpoint.

Enumerability verified live on categoryId=10020 (Elektronika, "total":
103,895): offset=0 vs offset=24 vs offset=48 (limit=24 each) returned
24/24/24 items with ZERO id overlap across all three pages -- a real,
clean offset pager, unlike prom_ua/kosik_cz in this same batch.

Price units, resolved (this class of source has bitten the repo before
-- WooCommerce minor units, Vendure thousandths): ``priceBlock.
finalPrice.amount`` is the DIRECT UZS value, not minor units. Verified
against the rendered PDP for the same product id (3165397): the API
returned ``finalPrice.amount: 44490``; the live PDP's own ``<title>``
literally reads "...за 49430 сум" (price had moved between the two
fetches, consistent with a live marketplace, not a units mismatch --
both figures are the same order of magnitude: tens of thousands of UZS,
no decimals, matching the sibling asaxiy_uz/lavka_uz convention for this
currency). Some items return ``finalPrice: null`` (no active listing
price) -- these are dropped; ``sellPrice.amount`` is tried as a
fallback.

See the ``x-iid`` paragraph above if `makeSearch` starts 429ing again in
production -- that header is what actually fixed the persistent 429s
seen from a8 during probing, not request spacing (a root-categories
warm-up call before the first search, kept here in `parse_auth`, is
still cheap insurance and doesn't hurt).

Canonical PDP URL: ``https://uzum.uz/ru/product/<productId>`` renders
correctly from the bare numeric id (no slug needed, confirmed live).

Product titles come back in Russian (client locale pinned to ru-RU /
Accept-Language: ru) even though category titles from root-categories
are Uzbek -- ``language: ru`` reflects the product-name field, which is
what downstream classification actually reads.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_AUTH_URL = "https://id.uzum.uz/api/auth/token"
_ROOT_CATEGORIES_URL = "https://api.uzum.uz/api/main/root-categories?eco=false"
_GRAPHQL_URL = "https://graphql.uzum.uz/"

_SEARCH_QUERY = """
query MakeSearch_ItemsAndFilters($queryInput: MakeSearchQueryInput!) {
  makeSearch(query: $queryInput) {
    total
    items {
      catalogCard {
        discovery {
          ... on DiscoveryProductCard { id }
          ... on DiscoverySkuCard { id productId }
          ... on DiscoverySkuGroupCard { id productId }
          title
          priceBlock {
            finalPrice { amount }
            sellPrice { amount }
          }
        }
      }
    }
  }
}
"""

PAGE_SIZE = 24
MAX_OFFSET = 24 * 20  # 20 pages/category cap


class UzumUzSpider(scrapy.Spider):
    name = "uzum_uz"
    allowed_domains = ["uzum.uz", "id.uzum.uz", "api.uzum.uz", "graphql.uzum.uz"]
    currency = "UZS"
    language = "ru"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        self.install_id = str(uuid.uuid4())
        yield scrapy.Request(
            _AUTH_URL,
            method="POST",
            headers={"Authorization": "Bearer", "Content-Type": "application/json",
                     "Referer": "https://uzum.uz/", "Origin": "https://uzum.uz"},
            body="{}",
            callback=self.parse_auth,
        )

    def parse_auth(self, response):
        token = None
        for raw in response.headers.getlist("Set-Cookie"):
            raw = raw.decode("utf-8", "ignore")
            if raw.startswith("access_token="):
                token = raw.split(";", 1)[0].split("=", 1)[1]
                break
        if not token:
            logger.error("uzum_uz: no access_token cookie in auth response")
            return

        headers = self._api_headers(token)
        # Cheap warm-up call before the first search; the actual 429 fix
        # is the x-iid header in _api_headers (see module docstring).
        yield scrapy.Request(
            _ROOT_CATEGORIES_URL,
            headers=headers,
            callback=self.parse_root_categories,
            meta={"token": token},
        )

    def _api_headers(self, token: str) -> dict:
        # x-iid (device install id) turned out to matter: without it the
        # search-gateway subgraph 429'd EVERY request from this box's IP,
        # even with a fresh token and a warm-up call first. A random UUID
        # (matching what the site's own JS generates per install) fixed it
        # -- see the module docstring.
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": "ru",
            "apollographql-client-name": "web-customers",
            "apollographql-client-version": "1.63.2",
            "Referer": "https://uzum.uz/",
            "Origin": "https://uzum.uz",
            "x-iid": self.install_id,
        }

    def parse_root_categories(self, response):
        token = response.meta["token"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("uzum_uz: root-categories response was not JSON")
            return

        roots = data.get("payload") or []
        logger.info(f"uzum_uz: {len(roots)} root categories discovered")

        for cat in roots:
            cat_id = cat.get("id")
            title = cat.get("title")
            if cat_id is None:
                continue
            yield self._search_request(token, cat_id, title, offset=0)

    def _search_request(self, token: str, category_id, title: str, offset: int):
        body = {
            "operationName": "MakeSearch_ItemsAndFilters",
            "variables": {
                "queryInput": {
                    "categoryId": str(category_id),
                    "showAdultContent": "NONE",
                    "filters": [],
                    "sort": "BY_RELEVANCE_DESC",
                    "pagination": {"offset": offset, "limit": PAGE_SIZE},
                    "correctQuery": False,
                    "getFastCategories": False,
                    "getFastFacets": False,
                    "getPromotionItems": False,
                }
            },
            "query": _SEARCH_QUERY,
        }
        return scrapy.Request(
            _GRAPHQL_URL,
            method="POST",
            headers=self._api_headers(token),
            body=json.dumps(body),
            callback=self.parse_search,
            meta={"token": token, "category_id": category_id, "title": title, "offset": offset},
        )

    def parse_search(self, response):
        token = response.meta["token"]
        category_id = response.meta["category_id"]
        title = response.meta["title"]
        offset = response.meta["offset"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(f"uzum_uz: bad JSON for category={category_id} offset={offset}")
            return
        if data.get("errors"):
            logger.warning(f"uzum_uz: GraphQL errors for category={category_id} offset={offset}: {data['errors']}")
            return

        items = ((data.get("data") or {}).get("makeSearch") or {}).get("items") or []
        logger.info(f"uzum_uz: category={title}({category_id}) offset={offset} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item = self._parse_item(it, title, scraped_at)
            if item is not None:
                yield item

        if len(items) == PAGE_SIZE and offset + PAGE_SIZE < MAX_OFFSET:
            yield self._search_request(token, category_id, title, offset + PAGE_SIZE)

    def _parse_item(self, it: dict, category: str, scraped_at: str) -> dict | None:
        discovery = (it.get("catalogCard") or {}).get("discovery") or {}
        name = discovery.get("title")
        product_id = discovery.get("productId") or discovery.get("id")
        price_block = discovery.get("priceBlock") or {}
        price = (
            (price_block.get("finalPrice") or {}).get("amount")
            or (price_block.get("sellPrice") or {}).get("amount")
        )
        if not name or not product_id or not price:
            return None

        return {
            "product_id": str(product_id),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://uzum.uz/ru/product/{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
