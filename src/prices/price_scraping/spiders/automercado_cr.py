"""
Auto Mercado (Costa Rica) - https://www.automercado.cr

Angular Universal storefront; the catalog is served by a public
Algolia search-only key embedded in the SPA's lazy chunk bundles
(app id FU5XFX7KNL, index "Product_CatalogueV2"). Queried directly -
no Playwright needed, no WAF in front of the Algolia CDN.

Empty-query pagination walks the whole catalog (nbHits ~19,053 @
100/page -> ~191 pages). Prices are CRC. Each hit carries a
`storeDetail` map keyed by 2-digit store id with a near-uniform
national price; a small minority of items omit some store ids, so we
take the lowest present store id as the canonical price rather than a
hardcoded "01". `amount` is the current effective (post-discount)
price; `basePrice` is the pre-discount shelf price.

The SPA has no static per-product route (every path we probed,
including plausible /producto/<id> and /p/<id> guesses, 200s to the
same Angular shell via catch-all SSR routing, so a GET to those paths
proves nothing). Product URLs are therefore built as a search deep
link on the SKU (`productNumber`), which is the real /buscar route on
the real domain and is unique per product for DuplicationPipeline
dedup purposes.

Category facet breakdown (from a live facet query) shows this is a
genuine grocery catalog, not general merchandise: ABARROTES 2904,
BEBIDAS NO ALCOHOLICAS 2353, LACTEOS Y EMBUTIDOS 1097, SNACK Y
GOLOSINA 1059, PANADERIA REPOSTERIA Y TORTILLAS 994, BEBIDAS
ALCOHOLICAS 623, CONGELADOS Y REFRIGERADOS 574, FRUTAS Y VERDURAS 543,
CARNES Y PESCADO 371, COMIDAS PREPARADAS 160 -- roughly 56% of the
19,053-row catalog is food/beverage by top-level category.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_ID = "FU5XFX7KNL"
_API_KEY = "335287091ff4a66858e0ad021ca45b76"
_INDEX = "Product_CatalogueV2"
_ENDPOINT = f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/{_INDEX}/query"
_HITS_PER_PAGE = 100
_MAX_PAGES = 500  # safety cap; nbPages ~191 at this page size


class AutomercadoCrSpider(scrapy.Spider):
    name = "automercado_cr"
    allowed_domains = ["algolia.net"]
    currency = "CRC"
    language = "es"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    def _headers(self):
        return {
            "X-Algolia-Application-Id": _APP_ID,
            "X-Algolia-API-Key": _API_KEY,
            "Content-Type": "application/json",
        }

    def _query(self, page):
        body = {"query": "", "hitsPerPage": _HITS_PER_PAGE, "page": page}
        return scrapy.Request(
            _ENDPOINT,
            method="POST",
            headers=self._headers(),
            body=json.dumps(body),
            callback=self.parse,
            meta={"page": page},
            dont_filter=True,
        )

    async def start(self):
        yield self._query(0)

    def parse(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.error("automercado_cr: non-JSON response at page %s", page)
            return

        hits = payload.get("hits", [])
        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            item = self._build(hit, scraped_at)
            if item:
                yield item

        if page == 0:
            nb_pages = min(payload.get("nbPages", 0), _MAX_PAGES)
            logger.info(
                "automercado_cr: nbHits=%s nbPages=%s",
                payload.get("nbHits"),
                nb_pages,
            )
            for p in range(1, nb_pages):
                yield self._query(p)

    def _build(self, hit, scraped_at):
        object_id = hit.get("objectID")
        name = hit.get("ecomDescription")
        if not object_id or not name:
            return None

        store_detail = hit.get("storeDetail") or {}
        if not store_detail:
            return None
        store_id = sorted(store_detail.keys())[0]
        store = store_detail[store_id]
        price = store.get("amount")
        if not price:
            return None

        category = (
            hit.get("parentProductid2") or ((hit.get("categoryPageId") or [None])[0])
        )
        sku = hit.get("productNumber") or object_id

        return {
            "product_id": str(object_id),
            "product_name": name.strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(store.get("productAvailable", True)),
            "url": f"https://www.automercado.cr/buscar?query={sku}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
