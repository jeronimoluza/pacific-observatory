"""
Farmatodo Colombia - https://www.farmatodo.com.co

Angular storefront; the product catalog is served by a public Algolia
search-only key embedded in the site's main JS bundle (app id VCOJEYD2PO,
index "products-colombia"). Queried directly - no Playwright, no WAF in
front of the Algolia CDN itself.

Empty-query pagination walks the whole catalog (nbHits ~154.7k @ 24/page).
Prices are COP; `offerPrice` is the current discounted price when set
(nonzero), else `fullPrice` is the regular price.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_ID = "VCOJEYD2PO"
_API_KEY = "eb9544fe7bfe7ec4c1aa5e5bf7740feb"
_INDEX = "products-colombia"
_ENDPOINT = f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/{_INDEX}/query"
_HITS_PER_PAGE = 100
_MAX_PAGES = 2000  # safety cap; nbPages ~1548 at this page size


class FarmatodoCoSpider(scrapy.Spider):
    name = "farmatodo_co"
    allowed_domains = ["algolia.net"]
    currency = "COP"
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
            logger.error("farmatodo_co: non-JSON response at page %s", page)
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
                "farmatodo_co: nbHits=%s nbPages=%s", payload.get("nbHits"), nb_pages
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
            "url": f"https://www.farmatodo.com.co/producto/{url_path}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
