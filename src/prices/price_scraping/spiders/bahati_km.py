"""
Bahati Marketplace (Comoros) — https://bahati-marketplace.tech/.

Comoros' fourth manifest and the first that is neither `coliscom_km`-style
diaspora-parcel nor a French-priced storefront: this platform runs a
dedicated Medusa v2 "Comores" region (`reg_01KKZ4732Y447ZQF7FRHXFYPK3`,
country=km) priced in KMF, distinct from its separate "Europe" region
(EUR, FR/DE/IT/ES/SE/GB/DK). A spot-check of the same product across both
regions found it priced in KMF only — the KMF region carries its own price
list, not a currency-converted mirror of the EUR one.

DISCOVERED via French-language search ("Anjouan Mohéli boutique en ligne
alimentation courses livraison") which surfaced "Bahati — Marketplace ·
Livraison · Grossistes aux Comores", advertised as delivering to Grande
Comore, Anjouan AND Mohéli — the first candidate found that names all three
islands rather than Moroni alone.

PLATFORM: Next.js storefront over a Medusa v2 backend, same-origin
(`/store/*` proxied through the Next.js host, not a separate API domain).
No public API discovery endpoint — the storefront's publishable API key
(`x-publishable-api-key`) is embedded in a Next.js JS chunk
(`ea220b36f5905c14.js` / `96ee2bd9ff4d3553.js` as of 2026-09-11) and is
required on every `/store/*` call or the API 400s with
`"Publishable API key required"`. This is the standard Medusa storefront
key, not a secret — it is shipped to every browser that loads the page.

    GET /store/products?limit=100&offset=<N>&region_id=<region>
    -> {"count", "products": [...]}

`region_id` is required to get `calculated_price` back per variant (the
resource docs advise `region_id` as the standard way to price a storefront
listing); without it, `variants[].calculated_price` doesn't resolve to a
price. Category assignment is empty on every product sampled (`categories:
[]`) — left null rather than invented, per house style.

SCOPE: the whole catalogue, deliberately unscoped, same call as
comoresenligne_km / kuuza_km. 198 products site-wide (measured 2026-09-11).
The catalogue is fashion/beauty-led (basketball shoes, skincare, boubous,
jewellery) with a THIN food tail — spot check found ~8 genuine food/drink
items (Thé marron, Thé rose, Sardine, Sel, Boisson Orange, Huile, Oignon)
against ~190 non-food rows. Non-food rows are wanted anyway; the classifier
assigns a leaf per product.

MULTI-VENDOR: the storefront's `/boutiques` nav implies distinct seller
storefronts under one platform (the GLOSSARY marketplace test) — channel
set to marketplace, not supermarket.

PRICING: `calculated_price.calculated_amount` is a plain integer in KMF
MAJOR units (KMF has no minor subunit in practice) — sampled at 25,000
(basketball shoes), 12,500 (body lotion), 3,000 (soap / gel), matching
plausible KMF retail prices with no minor-unit division needed.

Enumerability confirmed: offsets 0/50/100/150 each returned a disjoint
50-product slice (198 distinct product ids total, no repeats across pages).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://bahati-marketplace.tech"
API_PATH = "/store/products"
REGION_ID = "reg_01KKZ4732Y447ZQF7FRHXFYPK3"  # "Comores" region, currency=kmf
PUBLISHABLE_KEY = (
    "pk_fe6ddc606338de4dbd46027caa78f97d1bede81006327248945af548cb6bd7ee"
)
PAGE_SIZE = 100
MAX_PAGES = 20  # safety cap; 198 products is 2 pages at PAGE_SIZE=100


class BahatiKmSpider(scrapy.Spider):
    name = "bahati_km"
    allowed_domains = ["bahati-marketplace.tech"]
    currency = "KMF"
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
        fields = "id,title,handle,*variants.calculated_price"
        url = (
            f"{BASE_URL}{API_PATH}?limit={PAGE_SIZE}&offset={offset}"
            f"&region_id={REGION_ID}&fields={fields}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "Accept": "application/json",
                "Referer": f"{BASE_URL}/",
                "x-publishable-api-key": PUBLISHABLE_KEY,
            },
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

        products = payload.get("products") or []
        count = payload.get("count")
        found = 0

        for product in products:
            name = (product.get("title") or "").strip()
            pid = product.get("id")
            variants = product.get("variants") or []
            if not name or not pid or not variants:
                continue

            calc = (variants[0] or {}).get("calculated_price") or {}
            price = calc.get("calculated_amount")
            currency = (calc.get("currency_code") or self.currency).upper()
            if price is None:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue

            found += 1
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": None,
                "price": str(price),
                "currency": currency,
                "available": True,
                "url": f"{BASE_URL}/products/{pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: offset={offset} products={len(products)} "
            f"yielded={found} count={count}"
        )

        next_offset = offset + PAGE_SIZE
        if count is not None and next_offset < count and next_offset // PAGE_SIZE < MAX_PAGES:
            yield self._api_request(next_offset)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
