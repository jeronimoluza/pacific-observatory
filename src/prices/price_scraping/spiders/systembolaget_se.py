"""
Systembolaget (Sweden's state alcohol retail monopoly) —
https://www.systembolaget.se/.

Next.js storefront. All catalog rendering runs client-side against a public
API Management gateway:

    GET https://api-extern.systembolaget.se/sb-api-ecommerce/v1
        /productsearch/search?size=30&page=<N>
    header: Ocp-Apim-Subscription-Key: <key>

The subscription key is not a secret — it is inlined into the client bundle
at Next.js build time as `NEXT_PUBLIC_API_KEY_APIM` (verified live
2026-08-31: literal 32-char hex value baked into
/_next/static/chunks/1-cy4k4fw_1tj.js, the same value the site's own
browser JS attaches to every search request). No login, no session cookie.

The `size` query param is capped server-side at 30 regardless of the
requested value (tested 30/50/60 -> all return exactly 30 rows); pagination
must walk the `page` param instead. Verified live: pages 1-5 returned 150
distinct productIds with zero repeats, so `page` genuinely advances (unlike
the megamarche_ci offset trap). The walk stops when a page returns zero
products.

Full assortment, ~27,000 SKUs (metadata.docCount) covering wine, spirits,
beer, cider and alcohol-free alternatives -- this is the country's
beverage-of-record price source: Systembolaget is the sole legal retailer
of alcohol above 3.5% ABV in Sweden and publishes one national price list
(no store-level variation, unlike ICA/Coop).

Price is SEK, tax-inclusive, in `price` (float, major units). Currency is
not present per-row in the payload; SEK is the entire site's currency and
matches countries.yaml.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://api-extern.systembolaget.se/sb-api-ecommerce/v1/productsearch/search"
)
PDP_URL = "https://www.systembolaget.se/produkt/{number}/"
SUBSCRIPTION_KEY = "8d39a7340ee7439f8b4c1e995c8f3e4a"
PAGE_SIZE = 30


class SystembolagetSeSpider(scrapy.Spider):
    name = "systembolaget_se"
    allowed_domains = ["api-extern.systembolaget.se"]
    currency = "SEK"
    language = "sv"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page):
        return scrapy.Request(
            BASE_URL,
            callback=self.parse_page,
            errback=self.errback,
            headers={
                "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
                "Accept": "application/json",
            },
            meta={"page": page},
            dont_filter=True,
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON at page={page}")
            return

        products = data.get("products") or []
        for product in products:
            product_id = product.get("productId")
            price = product.get("price")
            if not product_id or price is None:
                continue
            name = " ".join(
                part
                for part in (
                    product.get("productNameBold"),
                    product.get("productNameThin"),
                )
                if part
            ).strip()
            if not name:
                continue
            category = " > ".join(
                filter(
                    None,
                    [
                        product.get("categoryLevel1"),
                        product.get("categoryLevel2"),
                    ],
                )
            )
            number = product.get("productNumber") or product_id
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": category or None,
                "price": str(price),
                "currency": self.currency,
                "available": not product.get("isCompletelyOutOfStock", False),
                "url": PDP_URL.format(number=number),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: page={page} got={len(products)} "
            f"docCount={data.get('metadata', {}).get('docCount')}"
        )

        if products:
            yield self._page_request(page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
