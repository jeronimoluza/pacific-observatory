"""
Spider for Danube (danube.sa) — Saudi Arabia hypermarket chain (Bindawood
Holding group).

Storefront is a Rails/Spree app (jQuery + Turbolinks, Spree.pathFor asset
bundle), but the actual product catalogue (category department pages,
search) is rendered client-side against a public Algolia index, NOT the
Spree JSON API. Found by grepping a category page
(/en/departments/cheese/dutch-cheese) for the instantsearch.js
initialisation block:

    var search = instantsearch({
      appId: '1D2IEWLQAD',
      apiKey: '87ca3b6b2ce56f0bb76fc194a8d170e2',   // search-only public key
      indexName: 'spree_products',
      ...
    })

Verified live 2026-08-31: `filters: "tenant_id = 1"` scopes the shared
`spree_products` index to Danube's own tenant (tenant_key "DAN" on every
returned hit) -- this is Danube's dedicated catalogue slice, not another
brand/country sharing the index. 33,161 total hits for tenant_id=1, real
grocery SKUs (e.g. Potatoe Baladi (Bag) 8.95 SAR, Banana (Tray) 9.95 SAR,
Samoli Bread Big 1.15 SAR), price/in_stock/master_id fields all present
and plausible.

Algolia's query endpoint refuses to paginate past 1,000 total hits for a
single filter (`you can only fetch the 1000 hits for this query`), and the
browse endpoint 403s for this search-only key -- so this spider partitions
the catalogue with a binary range split on the numeric `master_id` field
instead of a page counter: each request asks for a `master_id` range with
hitsPerPage=1000; if nbHits for that range is <=1000 (or the range has
shrunk to a single id) the hits are emitted directly from that same
response, otherwise the range is bisected and both halves are queried
again. This self-terminating recursive split needs no pre-known
category tree and cannot re-serve a window (each leaf range is disjoint by
construction) -- verified live: master_id values observed span from single
digits up to just under 100,000 (0 hits for master_id > 100000), so the
initial range is seeded generously at [0, 200000) to leave margin.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ALGOLIA_URL = "https://1D2IEWLQAD-dsn.algolia.net/1/indexes/spree_products/query"
_ALGOLIA_HEADERS = {
    "X-Algolia-Application-Id": "1D2IEWLQAD",
    "X-Algolia-API-Key": "87ca3b6b2ce56f0bb76fc194a8d170e2",
    "Content-Type": "application/json",
}
_TENANT_ID = 1
_INITIAL_LOW = 0
_INITIAL_HIGH = 200_000
_PRODUCT_BASE = "https://danube.sa"


class DanubeSaSpider(scrapy.Spider):
    name = "danube_sa"
    allowed_domains = ["algolia.net"]
    currency = "SAR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._range_request(_INITIAL_LOW, _INITIAL_HIGH)

    def _range_request(self, lo, hi):
        body = {
            "query": "",
            "hitsPerPage": 1000,
            "page": 0,
            "filters": f"tenant_id = {_TENANT_ID} AND master_id >= {lo} AND master_id < {hi}",
        }
        return scrapy.Request(
            _ALGOLIA_URL,
            method="POST",
            headers=_ALGOLIA_HEADERS,
            body=json.dumps(body),
            callback=self.parse_range,
            errback=self.errback,
            meta={"lo": lo, "hi": hi},
            dont_filter=True,
        )

    def parse_range(self, response):
        lo, hi = response.meta["lo"], response.meta["hi"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from range [{lo},{hi})")
            return

        nb_hits = data.get("nbHits", 0)
        if nb_hits == 0:
            return

        if nb_hits <= 1000 or hi - lo <= 1:
            if nb_hits > 1000:
                logger.warning(
                    f"{self.name}: range [{lo},{hi}) has {nb_hits} hits at min "
                    "width -- some products in this single master_id bucket "
                    "will be dropped by the 1000-hit cap"
                )
            for hit in data.get("hits", []):
                yield from self._item_from_hit(hit)
            logger.info(
                f"{self.name}: leaf range [{lo},{hi}) emitted {len(data.get('hits', []))}"
            )
        else:
            mid = (lo + hi) // 2
            yield self._range_request(lo, mid)
            yield self._range_request(mid, hi)

    def _item_from_hit(self, hit):
        name = (hit.get("full_name_en") or hit.get("name_en") or "").strip()
        price = hit.get("price")
        master_id = hit.get("master_id")
        url_en = hit.get("url_en")
        if not name or price is None or not master_id or not url_en:
            return
        yield {
            "product_id": str(master_id),
            "product_name": name[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": bool(hit.get("in_stock", True)),
            "url": f"{_PRODUCT_BASE}{url_en}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
