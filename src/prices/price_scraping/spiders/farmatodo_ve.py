"""
Farmatodo Venezuela - https://www.farmatodo.com.ve

Same Angular storefront family as farmatodo.com.co, but a distinct Algolia
index ("products-venezuela") behind the same app id (VCOJEYD2PO). Confirmed
2026-08-17 by pulling the search-only key straight out of the site's main
JS bundle; the CO probe only found the properties/store-locator key because
this products-venezuela query only fires from a live search-box interaction,
not a plain page load.

Prices are VES - confirmed via a product page's schema.org JSON-LD
(priceCurrency:"VES"), which matches the Algolia `fullPrice` value exactly.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_ID = "VCOJEYD2PO"
_API_KEY = "869a91e98550dd668b8b1dc04bca9011"
_INDEX = "products-venezuela"
_ENDPOINT = f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/{_INDEX}/query"
_HITS_PER_PAGE = 100
_MAX_PAGES = 2000  # safety cap; nbHits ~43.3k at this page size


class FarmatodoVeSpider(scrapy.Spider):
    name = "farmatodo_ve"
    allowed_domains = ["algolia.net"]
    currency = "VES"
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
            logger.error("farmatodo_ve: non-JSON response at page %s", page)
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
                "farmatodo_ve: nbHits=%s nbPages=%s", payload.get("nbHits"), nb_pages
            )
            for p in range(1, nb_pages):
                yield self._query(p)

    def _build(self, hit, scraped_at):
        name = hit.get("mediaDescription")
        if not name:
            return None
        full_price = hit.get("fullPrice")
        offer_price = hit.get("offerPrice")
        price = offer_price if offer_price else full_price
        if not price:
            return None
        url_path = hit.get("url")
        if not url_path:
            return None
        category = hit.get("categorie") or (hit.get("departments") or [None])[0]
        return {
            "product_id": str(hit.get("id")),
            "product_name": name.strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": hit.get("status") == "A",
            "url": f"https://www.farmatodo.com.ve/producto/{url_path}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
