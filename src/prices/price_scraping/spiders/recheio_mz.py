"""
RECHEIO Cash & Carry (Mozambique) - https://recheio.co.mz/.

Custom .NET storefront (not a known platform). The product listing/search
JS (js/ProductList.js) calls a JSON API with a hardcoded static token:

    POST /api/api/v2/Product/Search
    headers: {"lang": "1", "token": "1234567896543"}
    body: {"custId":0,"guestId":null,"currentpage":N,"vendorUrlKey":<store>,
           "pagesize":100,"minPrice":0,"maxPrice":10000000,
           "sortorder":{"field":"price","direction":"asc"},
           "filtervalues":"","searchstring":"","filter":{"category":null}}

`lang` must be the numeric locale id ("1"); the string "pt" 500s. Omitting
`vendorUrlKey` (or the whole request) returns an empty list even at 200 -
the storefront is scoped to a specific vendor/warehouse. Vendor keys come
from GET /api/api/v2/Vendor/vendorsList (Maputo Junta, Matola CMC, Nampula);
this spider uses Matola CMC (recheioccansmmatolacmc) per the candidate
brief. Each row carries `rc` = total matching record count, used to stop
paging. Product URL = https://recheio.co.mz/product/<urlKey>.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://recheio.co.mz"
_SEARCH_URL = f"{BASE_URL}/api/api/v2/Product/Search"
_VENDOR_URL_KEY = "recheioccansmmatolacmc"  # Matola CMC store
_PAGE_SIZE = 100


class RecheioMzSpider(scrapy.Spider):
    name = "recheio_mz"
    allowed_domains = ["recheio.co.mz"]
    currency = "MZN"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 4,
    }

    _HEADERS = {
        "lang": "1",
        "token": "1234567896543",
        "Content-Type": "application/json",
        "Referer": f"{BASE_URL}/products",
    }

    def start_requests(self):
        yield self._page_request(1)

    def _page_request(self, page):
        payload = {
            "custId": 0,
            "guestId": None,
            "currentpage": page,
            "vendorUrlKey": _VENDOR_URL_KEY,
            "pagesize": _PAGE_SIZE,
            "minPrice": 0,
            "maxPrice": 10000000,
            "sortorder": {"field": "price", "direction": "asc"},
            "filtervalues": "",
            "searchstring": "",
            "filter": {"category": None},
        }
        return scrapy.Request(
            _SEARCH_URL,
            method="POST",
            body=json.dumps(payload),
            headers=self._HEADERS,
            callback=self.parse_page,
            meta={"page": page},
            dont_filter=True,
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON response page={page}")
            return

        rows = (payload.get("Data") or {}).get("List") or []
        logger.info(f"{self.name}: page={page} rows={len(rows)}")
        if not rows:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            name = row.get("prName")
            url_key = row.get("urlKey")
            product_id = row.get("productId")
            if not name or not url_key or product_id is None:
                continue
            special = row.get("specialPrice") or 0
            unit = row.get("unitPrice") or 0
            price = special if special and special > 0 else unit
            if not price:
                continue
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": None,
                "price": str(price),
                "currency": self.currency,
                "available": row.get("stockAvailability") != "Out of Stock",
                "url": f"{BASE_URL}/product/{url_key}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        total = rows[0].get("rc") or 0
        if page * _PAGE_SIZE < total:
            yield self._page_request(page + 1)
