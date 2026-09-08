"""Spider for SuperPharm Trinidad -- https://superpharmtt.com/.

SuperPharm is a Trinidad & Tobago pharmacy chain that also carries a
grocery/household range ("Grocery", "Beverages", "Household Products"
sub-menus alongside pharmacy). Discovery lead (wave 4, bare hostname
`superpharmtt.com`, triage tier "C - engineering required").

**Bare SPA shell -> backend API, exactly the pattern the brief calls out.**
The site itself is an empty Quasar/Vue app (`<div id="q-app"></div>`, ~1.5KB
of HTML) -- `curl_cffi` alone sees nothing. A Playwright network trace of a
real UI click-path (Products -> Grocery -> Baking Supplies) found the
backend at `api.superpharmtt.com`, an AWS API Gateway + Lambda stack
(`Microsoft.Dynamics.Nav.Runtime` error strings in a couple of dead-end
probes -- the retail backend is Dynamics NAV/Business Central).

**Every call is a POST, not a GET** -- a bare `curl_cffi` GET on any
`/api/service/*` endpoint returns AWS API Gateway's generic
`{"message":"Missing Authentication Token"}`, which reads exactly like an
auth failure but is actually a method mismatch. No API key or session
cookie is required; the same POST body that the browser sends
(`{"appversion", "appID", "languageID"}`) works verbatim from plain
`curl_cffi`/`requests` with `Origin`/`Referer` headers set. No Playwright
needed at collection time.

**Category tree**: `POST /api/service/GetProductsHierarchy` returns the
full nested category tree (47 top-level categories, 260 leaves) in one
call -- walked once at spider start, no menu-clicking needed at runtime.

**Product listing**: `POST /api/search/GetProducts` (note: `search/`, not
`service/`) with `{"categoryId": "<leafNodeId>", "pageIdx": 0, "pageSize":
12, "storeNo": ""}` returns `{"totalCount", "pagesTotal", "products": [...]}`.
Guessing the sibling `service/GetProducts` endpoint (also live, also 200)
wastes cycles -- it wants a different, undocumented `filters.categories`
shape and never returned real rows in probing; `search/GetProducts` is the
one the app itself uses.

Page family parsed: API only (spider never fetches an HTML page).

Test run 2026-09-06 (--max-items 10): passed, real TTD prices (e.g. 27.00-
29.00 TTD for pantry items), matches the API sample seen during probing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://api.superpharmtt.com/api"
_SITE = "https://superpharmtt.com"
_APP_BODY = {"appversion": "2026.08.04.#2647", "appID": "1", "languageID": "EN-TT"}
_PAGE_SIZE = 24
_MAX_PAGES_PER_CATEGORY = 5  # safety cap


def _headers():
    return {
        "Referer": _SITE + "/",
        "Origin": _SITE,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }


def _leaf_node_ids(categories):
    leaves = []

    def walk(node):
        subs = node.get("subcategories") or []
        if not subs:
            leaves.append(node["nodeId"])
        for s in subs:
            walk(s)

    for c in categories:
        walk(c)
    return leaves


class SuperpharmttSpider(scrapy.Spider):
    name = "superpharmtt"
    allowed_domains = ["superpharmtt.com", "api.superpharmtt.com"]
    currency = "TTD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def start_requests(self):
        yield scrapy.Request(
            f"{_API_BASE}/service/GetProductsHierarchy",
            method="POST",
            headers=_headers(),
            body=json.dumps(_APP_BODY),
            callback=self.parse_hierarchy,
        )

    def parse_hierarchy(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("superpharmtt: hierarchy JSON decode failed")
            return
        categories = (data.get("productsHierarchy") or {}).get("categories") or []
        leaf_ids = _leaf_node_ids(categories)
        logger.info(f"superpharmtt: {len(leaf_ids)} leaf categories found")

        for node_id in leaf_ids:
            yield self._products_request(node_id, page_idx=0)

    def _products_request(self, node_id: str, page_idx: int):
        body = {
            **_APP_BODY,
            "categoryId": node_id,
            "pageIdx": page_idx,
            "pageSize": _PAGE_SIZE,
            "storeNo": "",
        }
        return scrapy.Request(
            f"{_API_BASE}/search/GetProducts",
            method="POST",
            headers=_headers(),
            body=json.dumps(body),
            callback=self.parse_products,
            meta={"node_id": node_id, "page_idx": page_idx},
        )

    def parse_products(self, response):
        node_id = response.meta["node_id"]
        page_idx = response.meta["page_idx"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"superpharmtt: products JSON decode failed for {node_id}")
            return

        products = data.get("products") or []
        pages_total = data.get("pagesTotal") or 1
        scraped_at = datetime.now(timezone.utc).isoformat()

        for prod in products:
            try:
                price_val = float(prod.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue
            name = (prod.get("productName") or "").strip()
            if not name:
                continue
            category = " > ".join(
                filter(None, [prod.get("categoryName"), prod.get("subCategoryName")])
            )
            yield {
                "product_id": prod.get("productNumber"),
                "product_name": name,
                "price": price_val,
                "currency": self.currency,
                "category": category or None,
                "url": f"{_SITE}/product/{prod.get('productNumber')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"superpharmtt: category={node_id} page={page_idx} "
            f"products={len(products)} pagesTotal={pages_total}"
        )

        next_page = page_idx + 1
        if products and next_page < pages_total and next_page < _MAX_PAGES_PER_CATEGORY:
            yield self._products_request(node_id, page_idx=next_page)
