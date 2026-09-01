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

FIXED 2026-08-31: this spider was left mid-work with no manifest and two
bugs. (1) `_page_request` built `scrapy.Request(BASE_URL, ...)` with no
query string at all, so every request hit the bare endpoint and silently
re-served page 1 forever (533 requests, 30 distinct items, all subsequent
rows dropped by the DuplicationPipeline as duplicate URLs) -- size/page
are now appended to the request URL as documented above. (2) The emitted
PDP url `produkt/{number}/` 404s -- the real site path is two segments,
`produkt/{category}/{slug}-{number}/`. Verified live: the site 200s on
ANY non-empty category/slug text as long as the trailing productNumber is
correct and the two-segment shape is present, so an ASCII-folded slug of
the product name (matching the site's own style, e.g. 'Bryggmästarens' ->
'bryggmastarens') is sufficient without reverse-engineering their exact
slug algorithm.

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
import re
import unicodedata
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://api-extern.systembolaget.se/sb-api-ecommerce/v1/productsearch/search"
)
PDP_URL = "https://www.systembolaget.se/produkt/{category}/{slug}-{number}/"
SUBSCRIPTION_KEY = "8d39a7340ee7439f8b4c1e995c8f3e4a"
PAGE_SIZE = 30


def _slugify(text, fallback="produkt"):
    """ASCII-fold and hyphenate; matches the site's own PDP slug style
    (e.g. 'Bryggmästarens' -> 'bryggmastarens'). Verified live 2026-08-31:
    the site 200s on ANY non-empty slug/category text as long as the
    trailing productNumber is correct and a two-segment /produkt/<a>/<b>-<n>/
    path shape is present -- so an approximate slug is sufficient to reach
    the real product page, it need not be pixel-exact.
    """
    if not text:
        return fallback
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or fallback


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
        url = f"{BASE_URL}?size={PAGE_SIZE}&page={page}"
        return scrapy.Request(
            url,
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
            url = PDP_URL.format(
                category=_slugify(product.get("categoryLevel1"), fallback="sortiment"),
                slug=_slugify(name),
                number=number,
            )
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": category or None,
                "price": str(price),
                "currency": self.currency,
                "available": not product.get("isCompletelyOutOfStock", False),
                "url": url,
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
