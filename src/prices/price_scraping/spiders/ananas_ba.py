"""
Spider for Ananas BiH (Bosnia and Herzegovina marketplace) —
https://ananas.ba/kategorije/hrana-i-pice.

Next.js storefront whose category *pages* are server-rendered (category
tree only, no products), but whose product *grid* is loaded client-side
via a public Algolia index. Found via Playwright network trace: the page
calls `POST https://y1bsbvj7ac-dsn.algolia.net/1/indexes/*/queries` with a
search-only API key embedded directly in the request URL
(`x-algolia-api-key=78d3f4f3befb3c4a68f4ebbf8c38fd81`,
`x-algolia-application-id=Y1BSBVJ7AC`, index
`prod_merchant_inventories_ba_bos`) -- no auth, no session, works from a
cold `curl_cffi` call. Verified live: `page=0`/`page=1` of the "Pivo"
(beer) leaf return disjoint hits (nbHits=52, nbPages=2, hitsPerPage=48),
e.g. "Tuborg pivo 0.33L flašica - pakovanje 24 komada" price=34.80,
merchant "EKO" (this is a multi-seller marketplace -- `merchant.displayName`
carries the actual first-party seller).

Category walk: the "Hrana i piće" (Food & drink) category page embeds its
depth-2 children (Piće, Kafa, Čaj, ...) in a `__NEXT_DATA__`
`dehydratedState` query result; each depth-2 category's own page then
embeds ITS children with full `breadcrumbs`, giving the three-level path
("Hrana i piće > Piće > Pivo") that the Algolia `filters` param requires
via `product.categories.lvl2`. Two-hop crawl: root -> each depth-2 page ->
Algolia query per depth-3 leaf, paginated to the query's own `nbPages`.
"""

import json
import logging
import re
import urllib.parse
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ROOT_URL = "https://ananas.ba/kategorije/hrana-i-pice"
_ALGOLIA_APP_ID = "Y1BSBVJ7AC"
_ALGOLIA_API_KEY = "78d3f4f3befb3c4a68f4ebbf8c38fd81"
_ALGOLIA_INDEX = "prod_merchant_inventories_ba_bos"
_ALGOLIA_URL = (
    f"https://y1bsbvj7ac-dsn.algolia.net/1/indexes/*/queries"
    f"?x-algolia-agent=Algolia&x-algolia-api-key={_ALGOLIA_API_KEY}"
    f"&x-algolia-application-id={_ALGOLIA_APP_ID}"
)
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
_ATTRS_TO_RETRIEVE = [
    "objectID",
    "price",
    "onSale",
    "onStock",
    "available",
    "product.name",
    "product.categoryNames",
    "merchant.displayName",
]
MAX_PAGES_PER_LEAF = 30  # safety cap


def _find_category_tree(next_data):
    queries = next_data.get("props", {}).get("pageProps", {}).get(
        "dehydratedState", {}
    ).get("queries", [])
    for q in queries:
        data = q.get("state", {}).get("data")
        if isinstance(data, dict):
            resp = data.get("response")
            if isinstance(resp, dict) and "children" in resp:
                return resp
    return None


class AnanasBaSpider(scrapy.Spider):
    name = "ananas_ba"
    allowed_domains = ["ananas.ba", "algolia.net"]
    currency = "BAM"
    language = "bs"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_ROOT_URL, callback=self.parse_root)

    def parse_root(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("ananas_ba: no __NEXT_DATA__ on %s", response.url)
            return
        next_data = json.loads(m.group(1))
        tree = _find_category_tree(next_data)
        if not tree:
            logger.warning("ananas_ba: no category tree on %s", response.url)
            return

        for child in tree.get("children", []):
            slug = child.get("slug")
            if not slug:
                continue
            yield scrapy.Request(
                f"https://ananas.ba/kategorije/{slug}",
                callback=self.parse_subcategory,
            )

    def parse_subcategory(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("ananas_ba: no __NEXT_DATA__ on %s", response.url)
            return
        next_data = json.loads(m.group(1))
        tree = _find_category_tree(next_data)
        if not tree:
            logger.warning("ananas_ba: no category tree on %s", response.url)
            return

        for leaf in tree.get("children", []):
            breadcrumbs = leaf.get("breadcrumbs") or []
            if not breadcrumbs:
                continue
            # breadcrumbs are ordered leaf -> root; reverse for top -> leaf
            names = [b["name"] for b in reversed(breadcrumbs)]
            lvl2_filter = " > ".join(names)
            yield self._algolia_request(lvl2_filter, page=0)

    def _algolia_request(self, lvl2_filter, page):
        params = urllib.parse.urlencode(
            {
                "attributesToRetrieve": json.dumps(_ATTRS_TO_RETRIEVE),
                "filters": f'product.categories.lvl2:"{lvl2_filter}"',
                "hitsPerPage": "48",
                "page": str(page),
            }
        )
        payload = {
            "requests": [{"indexName": _ALGOLIA_INDEX, "params": params}]
        }
        return scrapy.Request(
            _ALGOLIA_URL,
            method="POST",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            callback=self.parse_algolia,
            meta={"lvl2_filter": lvl2_filter, "page": page},
        )

    def parse_algolia(self, response):
        lvl2_filter = response.meta["lvl2_filter"]
        page = response.meta["page"]
        try:
            data = json.loads(response.text)
        except (ValueError, TypeError):
            logger.warning("ananas_ba: bad Algolia JSON for %s", lvl2_filter)
            return

        result = (data.get("results") or [{}])[0]
        hits = result.get("hits") or []
        nb_pages = result.get("nbPages") or 1
        logger.info(
            "ananas_ba: %s page=%d -> %d hits (nbPages=%s)",
            lvl2_filter,
            page,
            len(hits),
            nb_pages,
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            product = hit.get("product") or {}
            name = product.get("name")
            price = hit.get("price")
            if not name or price in (None, "", 0):
                continue
            yield {
                "product_id": hit.get("objectID"),
                "product_name": str(name).strip()[:500],
                "category": lvl2_filter.split(" > ")[-1],
                "price": str(price),
                "currency": self.currency,
                "available": bool(hit.get("available")) or bool(hit.get("onStock")),
                "url": f"https://ananas.ba/proizvod/x/{hit.get('objectID')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if hits and page + 1 < nb_pages and page + 1 < MAX_PAGES_PER_LEAF:
            yield self._algolia_request(lvl2_filter, page + 1)
