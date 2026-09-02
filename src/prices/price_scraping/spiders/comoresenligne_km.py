"""
Comores En Ligne (Comoros) — https://comores-en-ligne.fr/.

The Comoros' FIRST price source of any kind (the country had zero manifests
before this pass). A prior sweep found only `comoresmarket.com`, whose TLS
handshake fails on every impersonation profile, and recorded Comoros as a
dead end; this platform was never surfaced by that pass.

Next.js storefront — category pages server-render zero products and zero
price text, so an HTML spider sees nothing. A Playwright network capture
found a same-origin proxy in front of an open Django REST Framework API:

    GET /api-proxy/products?limit=100&offset=<N>[&category=<id>]
    -> {"count", "next", "previous", "results": [...]}

No auth, no cookie, no CSRF token. `count` is authoritative (1,527 products
site-wide as of 2026-09-01) and `offset` paginates cleanly.

Scope: the WHOLE catalogue, deliberately unscoped. The site is not food-led
(hygiene/beauty, small appliances, phones, construction materials, school
supplies all outrank food by product count), and only ~172 products sit in
the five food categories -- but non-food rows are wanted too, so no category
filter is applied and the classifier assigns leaves per product.

CURRENCY: the API returns an explicit `price.currency` of **EUR** on every
product, not the KMF that `countries.yaml` lists for Comoros. That is taken
at face value per the "use what the site returns" rule. The goods themselves
are physically in-country -- products carry a `stock_location` attribute of
"Grande Comore" / "Anjouan" and the `partners` array names Moroni and Ouani
stores -- but the platform bills in EUR because much of its custom is
diaspora paying from abroad. Same shape as `dokan_sy` (Syrian stock, USD
pricing), and cleaner than that case because KMF is on a fixed peg to EUR
(1 EUR = 491.96775 KMF), so the conversion carries no FX noise.

    >>> READ THIS BEFORE TRUSTING THE LEVELS <<<
    Whether diaspora-facing EUR pricing is an acceptable proxy for Comorian
    domestic retail is a DEFINITIONAL CALL that has not been ratified. If
    the answer is no, drop this manifest -- the country returns to zero
    sources. It is flagged in the Phase 8 report and in the inventory file.

`price.incl_tax` is used (a plain decimal string, no minor-unit trap).

IDENTITY TRAP: `slug` is NOT unique -- 43 slugs are reused across distinct
products (`carreau-m2` appears 12 times, `kabaila` 9, `carte-cadeau` 9).
Keying the emitted URL on the slug fed `DuplicationPipeline` (which dedups
on `item['url']`) 1,441 distinct URLs for 1,524 priced products and silently
lost 83 rows -- a first run reported exactly that before the cause was
traced. The API's own canonical per-product `url` field is used instead,
which is unique and real rather than a synthetic minted URL.

Verified live 2026-09-01: count=1527 site-wide; the five food categories
hold 172 distinct products (epicerie 91, produits-frais 33, cremerie 22,
les-boissons 20, boucherie 7) with sane staple pricing (Riz Ordinaire Narda
25KG EUR 28.02, Huile de Tournesol Fortune 1L EUR 3.65).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://comores-en-ligne.fr"
API_PATH = "/api-proxy/products"
PAGE_SIZE = 100
MAX_PAGES = 60  # safety cap; 1,527 products is ~16 pages at PAGE_SIZE=100


class ComoresEnLigneKmSpider(scrapy.Spider):
    name = "comoresenligne_km"
    allowed_domains = ["comores-en-ligne.fr", "www.comores-en-ligne.fr"]
    currency = "EUR"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._api_request(0)

    def _api_request(self, offset):
        return scrapy.Request(
            f"{BASE_URL}{API_PATH}?limit={PAGE_SIZE}&offset={offset}",
            callback=self.parse_api,
            errback=self.errback,
            headers={"Accept": "application/json", "Referer": f"{BASE_URL}/"},
            meta={"offset": offset},
            dont_filter=True,
        )

    def parse_api(self, response):
        offset = response.meta["offset"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        results = payload.get("results") or []
        found = 0

        for product in results:
            name = (product.get("title") or "").strip()
            pid = product.get("id")
            price_block = product.get("price") or {}
            price = price_block.get("incl_tax")
            if not name or pid is None or not price:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue

            categories = product.get("categories") or []
            availability = product.get("availability") or {}
            found += 1
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": categories[0] if categories else "",
                "price": str(price),
                "currency": price_block.get("currency") or self.currency,
                "available": bool(availability.get("is_available_to_buy", True)),
                "url": product.get("url")
                or f"{BASE_URL}/fr/catalogue/product/{product.get('slug') or pid}_{pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: offset={offset} results={len(results)} "
            f"yielded={found} count={payload.get('count')}"
        )

        if payload.get("next") and offset // PAGE_SIZE < MAX_PAGES:
            yield self._api_request(offset + PAGE_SIZE)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
