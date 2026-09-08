"""
LIMO Djibouti (multi-vendor marketplace) — https://limoo.online/ (canonical
storefront: https://www.limodjibouti.com/).

Shard entry point `limoo.online` is a pure client-side SPA shell with zero
server-rendered content; it links out to the real storefront domain
`www.limodjibouti.com`, which is built on the "Hyperzod" multi-vendor
marketplace SaaS. Backend API host `api.hyperzod.app` requires only an
`x-tenant: 6966` header (Djibouti tenant id) — no auth, no cookies, no WAF
encountered on either domain.

Two-step whole-marketplace walk (found via Playwright network trace, then
confirmed by reading the storefront's own JS bundle for its API client —
`cdn-store.hyperzod.app/assets/index-*.js` names every `/store/v1/...`
route including the one actually used here, `search/merchant/products`):

    POST /store/v1/recommend/merchants   {tenant_id, user_location, n<=100}
        -> up to 100 merchants with id, name, slug, product_count
    GET  /store/v1/search/merchant/products?merchant_id=<id>&page=<n>
        -> Laravel-paginated (current_page/last_page/per_page/total) product
           list for that ONE merchant, no category filter needed. Each row
           already carries flattened id/name/price/price_currency/in_stock
           fields (no need to dig into language_translation/product_pricing).

61 merchants observed 2026-09-06 spanning supermarkets, pharmacies,
electronics, restaurants and boutiques — e.g. "AlRayan Mall supermarché"
alone carries 1298 products. This is a genuine multi-vendor catalog (not a
curated storefront), so `channel: marketplace` and product names are
seller-authored; the classifier still assigns COICOP leaves per product.

Product URL is not a confirmed deep-link (the frontend route wasn't
recovered from the minified bundle in this pass) — constructed as the
merchant's storefront URL with a `?product_id=` query so every row still
gets a stable, unique URL for de-dup purposes.

Currency: DJF, read from each product's own `price_currency` field (matches
countries.yaml).
"""

import logging

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://api.hyperzod.app/store/v1"
STORE_BASE = "https://www.limodjibouti.com/fr/store"
TENANT_ID = 6966
# Djibouti city center; recommend/merchants needs *a* location to rank by,
# but with a large enough radius/`n` this returns the whole tenant roster.
USER_LOCATION = [11.5922966, 43.1460261]
MAX_MERCHANTS = 100  # API-enforced ceiling on `n`
MAX_PAGES_PER_MERCHANT = 200  # safety cap


class LimoDjSpider(scrapy.Spider):
    name = "limo_dj"
    allowed_domains = ["hyperzod.app"]
    currency = "DJF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _headers(self):
        return {"x-tenant": str(TENANT_ID), "Accept": "application/json"}

    async def start(self):
        yield scrapy.Request(
            f"{API_BASE}/recommend/merchants",
            method="POST",
            body=__import__("json").dumps(
                {
                    "tenant_id": TENANT_ID,
                    "user_id": None,
                    "user_location": USER_LOCATION,
                    "n": MAX_MERCHANTS,
                }
            ),
            headers={**self._headers(), "Content-Type": "application/json"},
            callback=self.parse_merchants,
            errback=self.errback,
        )

    def parse_merchants(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON merchant list response")
            return
        merchants = (payload.get("data") or {}).get("recommendations") or []
        logger.info(f"{self.name}: {len(merchants)} merchants found")
        for m in merchants:
            merchant_id = m.get("merchant_id") or m.get("id")
            slug = m.get("slug") or ""
            product_count = m.get("product_count") or 0
            if not merchant_id or not product_count:
                continue
            yield self._products_request(merchant_id, slug, 1)

    def _products_request(self, merchant_id, slug, page):
        url = (
            f"{API_BASE}/search/merchant/products"
            f"?merchant_id={merchant_id}&page={page}"
        )
        return scrapy.Request(
            url,
            headers=self._headers(),
            callback=self.parse_products,
            errback=self.errback,
            meta={"merchant_id": merchant_id, "slug": slug, "page": page},
            dont_filter=True,
        )

    def parse_products(self, response):
        merchant_id = response.meta["merchant_id"]
        slug = response.meta["slug"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON products response for {merchant_id}")
            return
        block = (payload.get("data") or {})
        rows = block.get("data") or []
        found = 0
        for p in rows:
            item = self._item(p, slug)
            if item:
                found += 1
                yield item
        logger.info(
            f"{self.name}: merchant={merchant_id} page={page} rows={len(rows)} "
            f"yielded={found} last_page={block.get('last_page')}"
        )
        last_page = block.get("last_page") or 1
        if page < min(last_page, MAX_PAGES_PER_MERCHANT):
            yield self._products_request(merchant_id, slug, page + 1)

    def _item(self, p, slug):
        pid = p.get("id") or p.get("product_id")
        name = p.get("name")
        price = p.get("price")
        if not pid or not name or price in (None, ""):
            return None
        try:
            if float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None
        return {
            "product_id": str(pid),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": p.get("price_currency") or self.currency,
            "available": bool(p.get("in_stock", True)),
            "url": f"{STORE_BASE}/{slug}?product_id={pid}" if slug else f"{STORE_BASE}/?product_id={pid}",
            "language": self.language,
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
