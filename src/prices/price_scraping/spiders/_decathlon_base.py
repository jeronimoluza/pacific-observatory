"""
Shared base class for Decathlon storefront spiders.

Decathlon's Next.js storefronts (Pages Router -- __NEXT_DATA__ present)
embed a search-only Algolia app id + API key directly in the page HTML as
`NEXT_PUBLIC_ALGOLIA_APP_ID` / `NEXT_PUBLIC_ALGOLIA_APP_KEY`. Verified open,
no auth beyond those two values, across 7 storefronts (TH, PH, ID, HK, TW,
AU, VN) as of 2026-08-07 -- all end-to-end smoke tested (358-1359 items
each at max-items 20, DuplicationPipeline never collapses them since every
hit carries a distinct product URL). Malaysia's decathlon.com.my did not
resolve (connection reset/timeout) -- not scaffolded. China's
decathlon.com.cn returned HTTP 406 -- not scaffolded, not investigated
further. **Keys are index-scoped per country** -- a key from one Decathlon
storefront 403s on a sibling storefront's index, so each subclass carries
its own app id / key / index name (do not share them).

The plain `query:""` search caps out at ~1000 results total (Algolia's
default pagination limit on the query endpoint, as opposed to the
admin-key-only `/browse` endpoint) even though `nbHits` reports the true
total. A whole-catalog crawl therefore partitions by the `sport_en` facet
(the only broadly-populated facetable attribute on this index; the root
value "sports" is the redundant top-of-tree bucket applied to nearly every
item and is skipped -- its children collectively cover the catalog, modulo
items with no sport_en at all). Each facet bucket is paged at
hitsPerPage=1000 up to MAX_PAGES_PER_FACET; overlap across buckets is
harmless because the DuplicationPipeline dedups on product URL. Taiwan's
index has no _en fields at all (Traditional-Chinese-only storefront) --
see LANG_SUFFIX / SPORT_FACET_FIELD below.

Subclasses set: name, allowed_domains, APP_ID, API_KEY, INDEX, BASE_URL,
currency, language (and LANG_SUFFIX/SPORT_FACET_FIELD for zh-only markets).
Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

HITS_PER_PAGE = 1000
MAX_PAGES_PER_FACET = 2
# Taiwan's index carries no _en fields at all (Traditional-Chinese-only
# storefront -- name_zh/url_zh/categoriesHierarchical_zh only). Request both
# suffixes plus the bare field so one ATTRS list covers every market;
# DecathlonBaseSpider.LANG_SUFFIX picks which one parse_page reads first.
ATTRS = [
    "objectID",
    "name_en",
    "name_zh",
    "name",
    "price",
    "currency",
    "url_en",
    "url_zh",
    "url",
    "categoriesHierarchical_en",
    "categoriesHierarchical_zh",
    "available",
]


class DecathlonBaseSpider(scrapy.Spider):
    name = None
    APP_ID: str = ""
    API_KEY: str = ""
    INDEX: str = ""
    BASE_URL: str = ""
    # Suffix of the localized fields to prefer (name_<suffix>, url_<suffix>,
    # categoriesHierarchical_<suffix>). "en" everywhere except Taiwan, whose
    # index has no _en fields at all -- see ATTRS comment above.
    LANG_SUFFIX: str = "en"
    # Facetable attribute used to partition the crawl. "sport_en" everywhere
    # except Taiwan ("sport_zh" -- no English facet on that index either).
    SPORT_FACET_FIELD: str = "sport_en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def _query_url(self):
        return f"https://{self.APP_ID}-dsn.algolia.net/1/indexes/{self.INDEX}/query"

    def _headers(self):
        return {
            "X-Algolia-API-Key": self.API_KEY,
            "X-Algolia-Application-Id": self.APP_ID,
            "Content-Type": "application/json",
        }

    async def start(self):
        self.seen_ids = set()
        body = {
            "query": "",
            "hitsPerPage": 0,
            "facets": [self.SPORT_FACET_FIELD],
            "maxValuesPerFacet": 1000,
            "attributesToHighlight": [],
        }
        yield scrapy.Request(
            self._query_url(),
            method="POST",
            headers=self._headers(),
            body=json.dumps(body),
            callback=self.parse_facets,
        )

    def parse_facets(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON facet response")
            return
        facet = (data.get("facets") or {}).get(self.SPORT_FACET_FIELD) or {}
        # The single largest bucket is the redundant root-of-tree value
        # (English "sports" / Chinese "運動") applied to nearly every item;
        # its children collectively cover the catalog. Skip by rank, not by
        # a hardcoded string, so this also works on non-English facets.
        ranked = sorted(facet.items(), key=lambda kv: -kv[1])
        values = [v for v, _ in ranked[1:]]
        logger.info(
            f"{self.name}: {len(values)} {self.SPORT_FACET_FIELD} facet buckets"
        )
        for value in values:
            yield self._page_request(value, 0)

    def _page_request(self, sport_value, page):
        body = {
            "query": "",
            "hitsPerPage": HITS_PER_PAGE,
            "page": page,
            "facetFilters": [[f"{self.SPORT_FACET_FIELD}:{sport_value}"]],
            "attributesToRetrieve": ATTRS,
            "attributesToHighlight": [],
        }
        return scrapy.Request(
            self._query_url(),
            method="POST",
            headers=self._headers(),
            body=json.dumps(body),
            callback=self.parse_page,
            meta={"sport_value": sport_value, "page": page},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        hits = data.get("hits") or []
        for hit in hits:
            product_id = hit.get("objectID")
            price = hit.get("price")
            if not product_id or product_id in self.seen_ids or price is None:
                continue
            self.seen_ids.add(product_id)

            suffix = self.LANG_SUFFIX
            name = (
                hit.get(f"name_{suffix}") or hit.get("name_en") or hit.get("name") or ""
            )
            url_path = (
                hit.get(f"url_{suffix}") or hit.get("url_en") or hit.get("url") or ""
            )
            cat_tree = (
                hit.get(f"categoriesHierarchical_{suffix}")
                or hit.get("categoriesHierarchical_en")
                or {}
            )
            path_tree = cat_tree.get("lvl2") or cat_tree.get("lvl1", "")

            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": path_tree,
                "price": str(price),
                "currency": hit.get("currency") or self.currency,
                "available": bool(hit.get("available", True)),
                "url": f"{self.BASE_URL}{url_path}" if url_path else self.BASE_URL,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        page = response.meta["page"]
        nb_pages = data.get("nbPages", 0)
        if page + 1 < min(nb_pages, MAX_PAGES_PER_FACET):
            yield self._page_request(response.meta["sport_value"], page + 1)
