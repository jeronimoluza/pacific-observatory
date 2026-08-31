"""
Spar Norge (NorgesGruppen), https://spar.no/ — Norway.

spar.no's own React/Next.js pages render nothing server-side (the "/varer"
listing is a client-hydrated skeleton -- "Laster produkter"/"Loading
products" -- with no data in the initial HTML, and its declared anonymous
accessTokenUrl (/api/auth/getToken) returns null with no browser session).
Network-traced live with Playwright on 2026-08-31: the hydrated page calls
the NorgesGruppen-wide product API directly, with NO auth header at all:

    GET https://platform-rest-prod.ngdata.no/api/products/{chainId}/{storeId}
        ?page=<n>&page_size=1000&full_response=true&fieldset=maximal
        &showNotForSale=true

chainId=1210 is Spar; storeId=7080001278137 is the specific store the site
defaulted to (GLN-style id) -- the same store's full assortment is returned
for every anonymous visitor (no session/geo needed to reproduce). This is
an Elasticsearch-backed endpoint: hits.total confirmed 6,947 products live,
page_size accepts up to 7000 in one call but is walked in 1,000-row pages
here to keep individual responses smaller. Each hit's _source carries
title, ean (barcode, used as product_id), pricePerUnit (the shelf price
for the unit sold -- verified against comparePricePerUnit/compareUnit for
weight-priced items, e.g. a 2.086kg cheese wheel: pricePerUnit=332.31,
comparePricePerUnit=159/kg, 332.31/2.086=159.3, consistent), categoryName,
isForSale/isOutOfStock, and slugifiedUrl (PDP path under https://spar.no/
varer). Sample verified: 'Banan' ean 4011 -> NOK 5.98; 'Norvegia 26%' ean
23027196 -> NOK 332.31 (2kg wheel). This is a real, wide grocery catalogue
(fruit/veg, dairy, cheese, eggs, meat, pantry) -- fruit, dairy and pantry
staples confirmed live. Same platform (api.ngdata.no) very likely serves
Meny/Kiwi/Joker with a different chainId -- worth reusing this endpoint
shape for those chains in a future pass.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CHAIN_ID = "1210"
_STORE_ID = "7080001278137"
_API_URL_TMPL = (
    "https://platform-rest-prod.ngdata.no/api/products/{chain_id}/{store_id}"
    "?page={page}&page_size=1000&full_response=true&fieldset=maximal"
    "&showNotForSale=true"
)
_MAX_PAGES = 20  # safety cap; ~7 pages covers the live 6,947-product catalogue


class SparNoSpider(scrapy.Spider):
    name = "spar_no"
    allowed_domains = ["ngdata.no"]
    currency = "NOK"
    language = "no"

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _API_URL_TMPL.format(chain_id=_CHAIN_ID, store_id=_STORE_ID, page=1),
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            data = json.loads(response.text)
        except (ValueError, TypeError):
            logger.warning(
                "spar_no: failed to parse JSON on page %s", response.meta["page"]
            )
            return

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total")
        page = response.meta["page"]
        logger.info("spar_no: page %d -> %d hits (total=%s)", page, len(hits), total)

        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            src = hit.get("_source", {})
            name = src.get("title")
            ean = src.get("ean")
            price = src.get("pricePerUnit")
            if not name or not ean or price in (None, "", 0):
                continue
            slug = src.get("slugifiedUrl") or ""
            yield {
                "product_id": str(ean),
                "product_name": str(name).strip()[:500],
                "category": src.get("categoryName"),
                "price": str(price),
                "currency": self.currency,
                "available": bool(src.get("isForSale")) and not src.get("isOutOfStock"),
                "url": f"https://spar.no/varer{slug}" if slug else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if hits and page < _MAX_PAGES and len(hits) == 1000:
            yield scrapy.Request(
                _API_URL_TMPL.format(
                    chain_id=_CHAIN_ID, store_id=_STORE_ID, page=page + 1
                ),
                callback=self.parse_page,
                meta={"page": page + 1},
            )
