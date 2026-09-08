"""Spider for tienda.claropr.com -- Claro Puerto Rico's device/accessory
online store.

claropr.com itself (the main telecom site) has no server-rendered prices
anywhere on its "Prepago"/"Pospago" plan pages -- pure marketing copy, a
"Ver Planes y Precios" button leads nowhere machine-readable. The actual
storefront with real prices is the separate `tienda.claropr.com` SPA
(device sales: phones, tablets, laptops, consoles, accessories), which
also renders no prices server-side.

Backend found via Playwright network capture on
tienda.claropr.com/home/telefonos/postpago/apple:
    POST https://tienda.claropr.com/api/Catalogue/listCatalogue
    body: {"catalogId":18,"pageNo":1,"pageItems":300,"creditClass":"C",
           "orderBy":7,"news":0,"offers":"0","categoryID":"0","brand":"",
           "filter":"","price":"","labels":[]}
Verified live 2026-09-06: 200, no auth beyond an `Origin` header, returns
ALL 7 sub-catalogs in one call (Postpago phones, Internet + Telefonía
bundles, Internet Inalámbrico, Tablets, Laptops, Consolas, Accesorios --
82 products total), not a curated homepage rail -- `pageItems: 300` with
brand/categoryID/price all left blank returns the full unfiltered set in
one page.

`creditClass` selects a financing tier (site defaults to "C") which
changes the displayed installment plan but NOT `regular_price` (the cash/
full price), which is what this spider emits -- so results are stable
across credit tiers. `salePrice` (0.0 when there is no active sale) is
used as the effective price when present and nonzero, else `regular_price`.

Currency: USD (Puerto Rico's own currency, matches countries.yaml).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://tienda.claropr.com/api/Catalogue/listCatalogue"
_BODY = {
    "catalogId": 18,
    "pageNo": 1,
    "pageItems": 300,
    "creditClass": "C",
    "orderBy": 7,
    "news": 0,
    "offers": "0",
    "categoryID": "0",
    "brand": "",
    "filter": "",
    "price": "",
    "labels": [],
}
_BASE = "https://tienda.claropr.com"


class ClaroprTiendaSpider(scrapy.Spider):
    name = "claropr_tienda"
    allowed_domains = ["claropr.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        yield scrapy.Request(
            _API,
            method="POST",
            headers={"Content-Type": "application/json", "Origin": _BASE},
            body=json.dumps(_BODY),
            callback=self.parse_catalogue,
        )

    def parse_catalogue(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response from {_API}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for top in data.get("catalogs") or []:
            for cat in top.get("catalog") or []:
                cat_name = cat.get("catalogName")
                for prod in cat.get("products") or []:
                    product_id = prod.get("productId")
                    name = prod.get("productName")
                    regular_price = prod.get("regular_price")
                    sale_price = prod.get("salePrice")
                    price = sale_price if sale_price else regular_price
                    if not (product_id and name and price):
                        continue
                    n += 1
                    yield {
                        "product_id": str(product_id),
                        "product_name": str(name).strip()[:500],
                        "category": cat_name,
                        "price": str(price),
                        "currency": self.currency,
                        "available": not prod.get("bitAllowBackOrder", False),
                        "url": f"{_BASE}/product/{product_id}",
                        "language": self.language,
                        "scraped_at_utc": scraped_at,
                        "brand": prod.get("brand"),
                    }
        logger.info(f"{self.name}: {n} rows from listCatalogue")
