"""
Spider for Coop Sverige (Sweden) -- https://www.coop.se/handla/.

Coop runs an EPiServer front-end over a hybris backend fronted by Azure API
Management at `external.api.coop.se`. The category pages render no prices in
SSR HTML (77 KB shell, zero `kr` matches), but a Playwright network trace on
2026-09-11 recovered the two calls the SPA actually makes, and both work over
plain HTTP with nothing but the public APIM subscription key that the site's
own JS bundle ships:

  1. GET  /ecommerce/coop/users/anonymous/categories/tree/<store>?api-version=v1
     -> {"nodes":[{"code","name","url","children":[...]}, ...]} -- 906 nodes,
        each `url` being the site-relative category path.
  2. POST /personalization/search/entities/by-attribute?api-version=v1&store=<store>...
     body {"attribute":{"name":"categoryIds","value":"<code>"},
           "resultsOptions":{"skip":N,"take":48,...}}
     -> {"results":{"count":<total>,"items":[...]}}

The key below is not a secret: it is embedded in the public storefront bundle
and sent by every anonymous browser session. Without it the API answers 401
"missing subscription key". Store 251300 is the default online store the
storefront selects for an anonymous visitor.

Enumerability proof (2026-09-11, category 6264 "Mjolk", count=106):
skip=0/48/96 returned 48/48/10 items with ZERO ean overlap between pages --
a real paginating catalogue, not a carousel.

Currency: SEK. `salesPriceData.b2cPrice` is already a decimal (16.27), NOT a
minor-unit integer -- verified against the rendered price on the Mjolk page.
`comparativePriceData` is the per-litre/kg unit price and is deliberately not
emitted as the product price.

Page family read: API (JSON), category-scoped. The payload carries no product
slug or PDP url (`url`/`code`/`productUrl` are all null on every item), so
`url` is set to the category listing page, as on hemkop_se.
"""

import json
import logging
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_API = "https://external.api.coop.se"
_SITE = "https://www.coop.se/handla"
_STORE = "251300"
# Public search-only APIM key from the storefront bundle (see docstring).
_SUB_KEY = "3becf0ce306f41a1ae94077c16798187"
_TREE_URL = (
    f"{_API}/ecommerce/coop/users/anonymous/categories/tree/{_STORE}?api-version=v1"
)
_SEARCH_URL = (
    f"{_API}/personalization/search/entities/by-attribute"
    f"?api-version=v1&store={_STORE}&groups=CUSTOMER_PRIVATE&device=desktop&direct=false"
)
_PAGE_SIZE = 48
_MAX_PAGES_PER_CATEGORY = 40  # 1,920 items; largest category observed is far below


class CoopSeSpider(scrapy.Spider):
    name = "coop_se"
    allowed_domains = ["external.api.coop.se"]
    currency = "SEK"
    language = "sv"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def _headers(self):
        return {
            "Ocp-Apim-Subscription-Key": _SUB_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.coop.se",
            "Referer": "https://www.coop.se/",
        }

    async def start(self):
        yield scrapy.Request(
            _TREE_URL,
            headers=self._headers(),
            callback=self.parse_tree,
            dont_filter=True,
        )

    def parse_tree(self, response):
        try:
            tree = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: category tree did not parse as JSON", self.name)
            return
        leaves = []

        def walk(nodes, path):
            for node in nodes or []:
                name = node.get("name")
                children = node.get("children") or []
                trail = path + ([name] if name else [])
                if children:
                    walk(children, trail)
                elif node.get("code"):
                    leaves.append((node["code"], " > ".join(trail), node.get("url")))

        walk(tree.get("nodes") or [], [])
        logger.info("%s: %d leaf categories", self.name, len(leaves))
        for code, trail, url in leaves:
            yield self._page_request(code, trail, url, 0)

    def _page_request(self, code, trail, cat_url, skip):
        body = {
            "attribute": {"name": "categoryIds", "value": code},
            "resultsOptions": {"skip": skip, "take": _PAGE_SIZE, "sortBy": [], "facets": []},
        }
        return scrapy.Request(
            _SEARCH_URL,
            method="POST",
            body=json.dumps(body),
            headers=self._headers(),
            callback=self.parse_products,
            cb_kwargs={"code": code, "trail": trail, "cat_url": cat_url, "skip": skip},
            dont_filter=True,
        )

    def parse_products(self, response, code, trail, cat_url, skip):
        if not response.text.strip():
            # A handful of pseudo-categories ("0001", "0002") answer 200 with
            # an empty body; not an error, just nothing to read.
            logger.debug("%s: empty search payload for %s", self.name, code)
            return
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning("%s: search payload for %s did not parse", self.name, code)
            return
        results = payload.get("results") or {}
        items = results.get("items") or []
        total = results.get("count") or 0
        if skip == 0:
            logger.info("%s: category %s (%s) -> %d items", self.name, code, trail, total)

        page_url = _SITE + cat_url if cat_url else _SITE + "/"
        for it in items:
            name = (it.get("name") or "").strip()
            price = (it.get("salesPriceData") or {}).get("b2cPrice")
            if not name or price is None:
                continue
            ean = it.get("ean") or it.get("id")
            # coop.se has no PDP route -- products render inline on the
            # paginated category listing (/handla/varor/<cat>/?page=N) and
            # every API item's url/code/productUrl is null. `url` is
            # therefore the browsable category page plus a synthetic ?ean=
            # suffix, which exists only to give each row a unique identity:
            # DuplicationPipeline dedups on url and would otherwise collapse
            # each category to one row. Query strings are excluded from
            # archive_path_re matching, so CC resolution is unaffected.
            yield {
                "product_id": ean,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": trail or None,
                "url": f"{page_url}?ean={quote(str(ean))}" if ean else page_url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        next_skip = skip + _PAGE_SIZE
        if items and next_skip < total and next_skip < _PAGE_SIZE * _MAX_PAGES_PER_CATEGORY:
            yield self._page_request(code, trail, cat_url, next_skip)
