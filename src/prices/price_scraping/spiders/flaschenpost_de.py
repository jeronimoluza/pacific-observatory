"""
Spider for Flaschenpost (Germany) -- https://www.flaschenpost.de/.

The PDP is a client-rendered Vue SPA shell (no price in the raw HTML), but
the shell embeds the numeric commercetools `productId` in an inline
`<script type="application/json">` block. Playwright network-capture
(2026-09-06) found the real pricing endpoint behind it:

  GET /php-product-api/v1/products/pdp/warehouse/1?ids=<productId>
      -> [{"key","name":{"de-DE":...},"categories":[...],
           "masterVariant":{"price":{"value":{"centAmount","currencyCode",
           "fractionDigits"}}}}]

This endpoint is plain HTTP, no auth, warehouse=1 (Berlin, the default/
largest warehouse) hardcoded -- confirmed live 2026-09-06. It does NOT
batch: repeated `ids=` params or `ids[]=` syntax both silently drop to a
single result, so this is a two-hop-per-product crawl (fetch the PDP HTML
to read `productId`, then call the API for price) rather than the
batched-card pattern used by the Rohlik-family spiders. `sitemap_p.xml`
lists ~4,150 canonical PDP URLs; some entries there 404 (discontinued
SKUs still enumerated) and are skipped.

Confirmed live 2026-09-06: productId 5648 "Mio Mio Mate Zero" EUR 12.99
(centAmount 1299, fractionDigits 2); productId 8068 "Sprehe Feinkost
Pfannengyros Hähnchen".
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.flaschenpost.de"
_SITEMAP_URL = f"{_BASE}/sitemap_p.xml"
_PRODUCT_ID_RE = re.compile(r'"productId":(\d+)')
MAX_PRODUCTS = 6000  # safety cap; sitemap currently ~4,150


class FlaschenpostDeSpider(scrapy.Spider):
    name = "flaschenpost_de"
    allowed_domains = ["flaschenpost.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = re.findall(r"<loc>(.*?)</loc>", response.text)
        urls = urls[:MAX_PRODUCTS]
        logger.info(f"flaschenpost_de: sitemap yielded {len(urls)} product urls")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_pdp_shell,
                meta={"handle_httpstatus_list": [404]},
            )

    def parse_pdp_shell(self, response):
        if response.status == 404:
            return
        m = _PRODUCT_ID_RE.search(response.text)
        if not m:
            logger.warning(f"no productId found at {response.url}")
            return
        pid = m.group(1)
        yield scrapy.Request(
            f"{_BASE}/php-product-api/v1/products/pdp/warehouse/1?ids={pid}",
            callback=self.parse_product_api,
            meta={"pdp_url": response.url},
        )

    def parse_product_api(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        if not data:
            return
        p = data[0]
        variant = p.get("masterVariant") or {}
        price_block = variant.get("price") or {}
        value = price_block.get("value") or {}
        cent = value.get("centAmount")
        if cent is None:
            return
        fraction_digits = value.get("fractionDigits", 2)
        price = cent / (10**fraction_digits)
        if price <= 0:
            return
        name = (p.get("name") or {}).get("de-DE")
        if not name:
            return
        cats = p.get("categories") or []
        category = None
        if cats:
            obj = cats[0].get("obj") or {}
            cat_name = (obj.get("name") or {}).get("de-DE")
            if cat_name:
                category = cat_name
        yield {
            "product_id": str(p.get("key") or variant.get("sku") or ""),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": value.get("currencyCode", self.currency),
            "available": True,
            "url": response.meta["pdp_url"],
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
