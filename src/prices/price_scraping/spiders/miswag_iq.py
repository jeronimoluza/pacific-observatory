"""
Spider for miswag.net / miswag.com — Iraq marketplace (Nuxt.js storefront-web-app
v5.0.53). The .net domain the shard names redirects/serves the same app as
.com; robots.txt on .net points at a sitemap that 404s, so all requests below
use miswag.com directly.

Every content API call (`/content/v1/...`) requires an `Authorization: Bearer
<JWT>` + `client-id: 4` + `bundle-version: 5.0.0` header set. The JWT
(HS256, claims `iat`/`uid`/`tok`/`did`/`iss`/`sc` -- confirmed live 2026-08-17
via jwt.io-style base64 decode) carries **no `exp` claim**, but it is minted
entirely client-side on page load and there is no public endpoint that mints
one from a plain HTTP call (the `/auth-api/v1/guest` endpoint the shard probe
found is a registration ping, not a token issuer -- it requires the same
bearer token to call, confirmed via network-order trace). Since we cannot
prove it is safe to hardcode, this spider fetches a fresh token every run: a
single scrapy-playwright bootstrap request loads the homepage, reads the
`__anonToken` cookie Playwright's browser context sets, and every subsequent
request in the crawl (plain curl-speed scrapy.Request, no browser) replays
that header set. Confirmed live: a token minted this way authenticates
successfully against `/content/v1/l1_categories` etc. via curl_cffi outside
the browser entirely.

Catalog walk: `/content/v1/l1_categories` (id/alias per top department) ->
`/content/v1/l1_categories/<alias>` (a CMS page-builder response; product
CATEGORY tiles are marked `"action":{"target":"collection","id":"<cid>"}`,
extracted by walking the JSON for that shape) -> `/content/v1/collections/
<cid>?cursor=<base64 {"per_page":16,"page":N}>` -- a real product listing
with price/currency/category/url per row and page-based cursor pagination.
Confirmed live: collection "tablets-smartphones-tab" page 1 vs page 2
returned disjoint product-id sets (materially different), and page 2's own
response carries a `page:3` cursor for further paging -- a genuine walkable
catalog, not a carousel.

Prices are in IQD (Iraqi dinar), confirmed from the `price.currency` field
on live rows (e.g. a Samsung Galaxy A16 listing at IQD 227,000).
"""

import base64
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://miswag.com"
_PER_PAGE = 16
_MAX_PAGES_PER_COLLECTION = 30  # safety cap


def _cursor(page: int) -> str:
    raw = json.dumps({"per_page": _PER_PAGE, "page": page}).encode()
    return base64.b64encode(raw).decode()


def _find_collection_ids(node, out: set):
    if isinstance(node, dict):
        action = node.get("action")
        if isinstance(action, dict) and action.get("target") == "collection":
            cid = action.get("id")
            if cid:
                out.add(cid)
        for v in node.values():
            _find_collection_ids(v, out)
    elif isinstance(node, list):
        for v in node:
            _find_collection_ids(v, out)


class MiswagIqSpider(scrapy.Spider):
    name = "miswag_iq"
    allowed_domains = ["miswag.com"]
    currency = "IQD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/en",
            callback=self.parse_bootstrap,
            meta={"playwright": True, "playwright_include_page": True},
        )

    async def parse_bootstrap(self, response):
        page = response.meta["playwright_page"]
        try:
            cookies = await page.context.cookies()
        finally:
            await page.close()
        token = next((c["value"] for c in cookies if c["name"] == "__anonToken"), None)
        if not token:
            logger.warning("miswag_iq: no __anonToken cookie minted, aborting")
            return
        self.auth_headers = {
            "authorization": f"Bearer {token}",
            "client-id": "4",
            "bundle-version": "5.0.0",
        }
        yield scrapy.Request(
            f"{_BASE}/content/v1/l1_categories",
            callback=self.parse_l1_categories,
            headers=self.auth_headers,
        )

    def parse_l1_categories(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        items = ((data.get("data") or {}).get("content")) or []
        aliases = [i.get("alias") for i in items if i.get("alias")]
        logger.info(f"miswag_iq: {len(aliases)} l1 category aliases")
        for alias in aliases:
            yield scrapy.Request(
                f"{_BASE}/content/v1/l1_categories/{alias}",
                callback=self.parse_l1_detail,
                headers=self.auth_headers,
            )

    def parse_l1_detail(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        collection_ids = set()
        _find_collection_ids(data.get("data"), collection_ids)
        if not hasattr(self, "_seen_collections"):
            self._seen_collections = set()
        new_ids = collection_ids - self._seen_collections
        self._seen_collections |= new_ids
        for cid in new_ids:
            yield scrapy.Request(
                f"{_BASE}/content/v1/collections/{cid}?cursor={_cursor(1)}",
                callback=self.parse_collection,
                headers=self.auth_headers,
                meta={"collection_id": cid, "page": 1},
            )

    def parse_collection(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        block = data.get("data") or {}
        rows = block.get("content") or []
        cid = response.meta["collection_id"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            price = row.get("price") or {}
            value = price.get("value")
            title = (row.get("title") or {}).get("EN") or (row.get("title") or {}).get(
                "AR"
            )
            product_id = row.get("id") or row.get("slug")
            if not (title and value and product_id):
                continue
            yield {
                "product_id": str(product_id),
                "product_name": str(title).strip()[:500],
                "category": row.get("category"),
                "price": str(value),
                "currency": price.get("currency") or self.currency,
                "available": bool(row.get("is_available", True)),
                "url": row.get("url") or f"{_BASE}/products/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"miswag_iq: collection={cid} page={page} rows={len(rows)}")
        if len(rows) >= _PER_PAGE and page < _MAX_PAGES_PER_COLLECTION:
            yield scrapy.Request(
                f"{_BASE}/content/v1/collections/{cid}?cursor={_cursor(page + 1)}",
                callback=self.parse_collection,
                headers=self.auth_headers,
                meta={"collection_id": cid, "page": page + 1},
            )
