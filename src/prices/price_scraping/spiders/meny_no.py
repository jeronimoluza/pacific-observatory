"""
Meny (NorgesGruppen), https://meny.no/ — Norway.

meny.no/nettbutikk is a client-hydrated shell with no product data in the
raw HTML, but the same NorgesGruppen-wide product API already confirmed
for spar_no serves this chain too -- just a different chainId. Network
traced live with Playwright on 2026-09-06: the hydrated page calls

    GET https://platform-rest-prod.ngdata.no/api/products/{chainId}/{storeId}
        ?page=<n>&page_size=1000&full_response=true&fieldset=maximal
        &showNotForSale=true

with chainId=1300 (Meny) and storeId=7080001150488, NO auth header, same
Elasticsearch-backed shape as spar_no (hits.total, hits.hits[]._source).
Verified live: hits.total=11,814 products; sample "Bananer" ean=4011 ->
NOK 5.98, "Norsk agurk" ean=4595 -> NOK 29.90. Reuses the exact spar_no.py
pattern per that spider's own docstring note that other NorgesGruppen
chains share this endpoint shape.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CHAIN_ID = "1300"
_STORE_ID = "7080001150488"
_API_URL_TMPL = (
    "https://platform-rest-prod.ngdata.no/api/products/{chain_id}/{store_id}"
    "?page={page}&page_size=1000&full_response=true&fieldset=maximal"
    "&showNotForSale=true"
)
_MAX_PAGES = 20  # safety cap; ~12 pages covers the live ~11.8k-product catalogue


class MenyNoSpider(scrapy.Spider):
    name = "meny_no"
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
                "meny_no: failed to parse JSON on page %s", response.meta["page"]
            )
            return

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total")
        page = response.meta["page"]
        logger.info("meny_no: page %d -> %d hits (total=%s)", page, len(hits), total)

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
                "url": f"https://meny.no/varer{slug}" if slug else response.url,
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
