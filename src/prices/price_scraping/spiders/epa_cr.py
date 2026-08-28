"""
Spider for EPA en Linea (Costa Rica) -- https://cr.epaenlinea.com/.

Shard listed the apex `epaenlinea.com` domain; the apex is a country-selector
page with no catalog of its own and 301s any /productos/<slug>.html request
to the matching top-level slug on the country subdomain (verified live
2026-08-17: /productos/ferreteria-y-cerrajeria.html -> /ferreteria-y-cerrajeria.html
on cr.epaenlinea.com). Onboarded on the Costa Rica subdomain directly, not
the apex -- the shard's other listed candidate, Venezuela, has no equivalent
subdomain confirmed live.

Home-improvement / hardware chain (Magento 2, standard SSR product grid),
NOT grocery -- the shard's `catalog: grocery` is wrong; the real top-nav
taxonomy (banos, construccion, electricidad, ferreteria-y-cerrajeria,
herramientas, plomeria, ...) is hardware/home-improvement. `channel` is set
accordingly.

Standard Magento markup: `li.product-item`, price in
`.price-final_price [data-price-amount]` (colones symbol confirms CRC).
Product identity uses the add-to-cart form's `data-product-sku` (stable
SKU) rather than the numeric entity id embedded in the price span's DOM id.
Pagination is `?p=N`.
"""

from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_BASE = "https://cr.epaenlinea.com"
_CATEGORIES = [
    "banos",
    "cocinas",
    "construccion",
    "decoracion",
    "electricidad",
    "electrodomesticos",
    "exteriores",
    "ferreteria-y-cerrajeria",
    "herramientas",
    "lamparas",
    "limpieza",
    "maderas-y-puertas",
    "muebles-y-organizacion",
    "pinturas",
    "pisos",
    "plomeria",
    "seguridad",
]
MAX_PAGES_PER_CATEGORY = 20


class EpaCrSpider(scrapy.Spider):
    name = "epa_cr"
    allowed_domains = ["epaenlinea.com"]
    currency = "CRC"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}.html",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        items = response.css("li.product-item")
        for item in items:
            href = item.css("a.product-item-link::attr(href)").get()
            name = item.css("a.product-item-link::text").get()
            name = (name or "").strip()
            if not href or not name:
                continue
            amount = item.css(
                ".price-final_price [data-price-amount]::attr(data-price-amount)"
            ).get()
            if not amount:
                continue
            sku = item.css("[data-product-sku]::attr(data-product-sku)").get()
            product_id = sku or href
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": slug,
                "price": amount,
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if items and page < MAX_PAGES_PER_CATEGORY:
            next_href = response.css("a.action.next::attr(href)").get()
            if next_href:
                yield scrapy.Request(
                    urljoin(_BASE, next_href),
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page + 1},
                )
