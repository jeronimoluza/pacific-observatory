"""
Inkafarma (Peru) - https://inkafarma.pe

Angular SPA over a mixed backend; catalog search runs on Algolia (app id
15W622LAQ4, index "products"), key pulled from the site's main JS bundle
2026-08-17. The AWS Lambda product-detail API the original probe tried is a
dead end (200/content-length:0 even with a valid session); Algolia is the
practical scrape surface.

Empty-query pagination walks the whole catalog (nbHits ~45.9k @ 100/page).
Prices are PEN (`priceList`, the regular shelf price before any loyalty-card
discount). No priceCurrency field is exposed by the API or a server-rendered
PDP (the product page is a client-rendered shell) - PEN is Peru's official
currency and matches the price magnitudes observed.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_ID = "15W622LAQ4"
_API_KEY = "3ba15abece13b00b123c5501680690f7"
_ENDPOINT = f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/products/query"
_HITS_PER_PAGE = 100
_MAX_PAGES = 2000  # safety cap; nbHits ~45.9k at this page size


class InkafarmaPeSpider(scrapy.Spider):
    name = "inkafarma_pe"
    allowed_domains = ["algolia.net"]
    currency = "PEN"
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
            logger.error("inkafarma_pe: non-JSON response at page %s", page)
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
                "inkafarma_pe: nbHits=%s nbPages=%s", payload.get("nbHits"), nb_pages
            )
            for p in range(1, nb_pages):
                yield self._query(p)

    def _build(self, hit, scraped_at):
        name = hit.get("name")
        price = hit.get("priceList")
        if not name or not price:
            return None
        category = " > ".join(hit.get("category") or []) or None
        uri = hit.get("uri")
        return {
            "product_id": str(hit.get("objectID")),
            "product_name": name.strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://inkafarma.pe/producto/{uri}" if uri else None,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
