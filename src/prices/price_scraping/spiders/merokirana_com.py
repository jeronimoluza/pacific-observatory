"""
Spider for MeroKirana — https://merokirana.com/.

Create-react-app SPA over a proprietary POST-based query protocol called
"Semantro" (`https://merokirana.com/semantro-web-interface/query`, JSON-LD
-flavoured envelopes, `multipart/form-data` with a single `data` field).
Platform fingerprint worth recording: this is the only site seen in this
pass using Semantro -- action names (`listBaseCategories`,
`listCategoryProducts`, `getProductData`, ...) were recovered from the
`actionName` strings baked into `static/js/main.*.js`.

Two-step harvest, because the listing action omits price:
  1. `listBaseCategories` -> category identifiers.
  2. `listCategoryProducts` (paged via `pageLimit.start/end`) -> product
     identifiers + name/brand/tags, NO price.
  3. `getProductData` (one call per product) -> `price` + `priceCurrency`
     ("NRs.").

Verified live 2026-09-06: `listBaseCategories` -> 9 top-level categories
incl. "Grocery", "Bakery & Dairy", "Beverage". `listCategoryProducts` for
"Grocery" (pageLimit 0-20) -> 20 products, e.g. "Navaras Kwati, 500gm".
`getProductData` for one of those -> {"price": 1650.0, "priceCurrency":
"NRs."}. curl_cffi + `CurlMime` multipart works cold, no cookies/session
needed.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://merokirana.com"
_QUERY_URL = f"{_BASE}/semantro-web-interface/query"
_CTX = "http://semantro.com/"
_PAGE_SIZE = 20


def _envelope(action_name, data=None, page_start=None, page_end=None):
    payload = {"@context": _CTX, "@type": "KiranaSearch", "actionName": action_name}
    if page_start is not None:
        payload["pageLimit"] = {
            "@context": _CTX,
            "@type": "PageProperty",
            "start": page_start,
            "end": page_end,
        }
    if data is not None:
        payload["data"] = data
    return payload


def _multipart_body(payload):
    """Build a multipart/form-data body for a single `data` field by hand
    (Scrapy's FormRequest doesn't support arbitrary multipart parts)."""
    boundary = "----ScrapyBoundaryMeroKirana"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="data"\r\n\r\n'
        f"{json.dumps(payload)}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    return body, headers


class MerokiranaComSpider(scrapy.Spider):
    name = "merokirana_com"
    allowed_domains = ["merokirana.com"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _query_request(self, payload, callback, meta=None):
        body, headers = _multipart_body(payload)
        return scrapy.Request(
            _QUERY_URL,
            method="POST",
            body=body,
            headers=headers,
            callback=callback,
            meta=meta or {},
        )

    async def start(self):
        yield self._query_request(
            _envelope("listBaseCategories"), callback=self.parse_categories
        )

    def parse_categories(self, response):
        data = json.loads(response.text)
        cats = data.get("itemListElement", [])
        logger.info(f"merokirana_com: {len(cats)} base categories")
        for cat in cats:
            identifier = cat.get("identifier")
            if not identifier:
                continue
            yield self._query_request(
                _envelope(
                    "listCategoryProducts",
                    data={
                        "@context": _CTX,
                        "@type": "KiranaCategory",
                        "identifier": identifier,
                    },
                    page_start=0,
                    page_end=_PAGE_SIZE,
                ),
                callback=self.parse_category_products,
                meta={"category": cat.get("categoryName")},
            )

    def parse_category_products(self, response):
        category = response.meta["category"]
        data = json.loads(response.text)
        products = data.get("itemListElement", [])
        logger.info(f"merokirana_com: category={category} products={len(products)}")
        for p in products:
            identifier = p.get("identifier")
            product_id = p.get("productID")
            if not identifier or not product_id:
                continue
            yield self._query_request(
                _envelope(
                    "getProductData",
                    data={
                        "@context": "http://semantro.com",
                        "@type": "KiranaProduct",
                        "identifier": identifier,
                        "productID": product_id,
                    },
                ),
                callback=self.parse_product_data,
                meta={
                    "category": category,
                    "identifier": identifier,
                    "product_id": product_id,
                    "product_name": p.get("productName"),
                    "brand": p.get("brandName"),
                },
            )

    def parse_product_data(self, response):
        meta = response.meta
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            return
        price = data.get("price")
        if price is None:
            return
        name = meta.get("product_name") or ""
        brand = meta.get("brand")
        if brand and brand not in name:
            name = f"{brand} {name}".strip()
        yield {
            "product_id": meta["product_id"],
            "product_name": name.strip()[:500],
            "category": meta.get("category"),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/product/{meta['identifier']}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
