"""
Shared base class for CaribeEats (backend.caribeeats.com) business storefronts.

CaribeEats is a Wolt/Glovo-style delivery aggregator covering several
Eastern Caribbean territories (Grenada, St Kitts, Nevis, Dominica, St Lucia,
Barbados, Trinidad, Jamaica, Guyana, Bahamas, BVI, Antigua, Montserrat,
Anguilla, St Eustatius -- confirmed live via /api/init as of 2026-09-01).
Named vendor storefronts on the platform (independent supermarkets, liquor
stores, fishmongers, a CaribeEats-operated general-goods shop branded
"CaribeShop") each expose their FULL catalogue in a single unauthenticated
GET to /api/business/<slug> -- no pagination, no auth, no location gate
(the consumer-facing web app gates the *business directory* behind a
geolocation prompt -- see known_blockers.md CaribeEats/LocalExpress
section -- but the per-business detail endpoint itself is open once you
have the slug).

Response shape: {"currency": "<ISO4217>", "categories": [{"name": ...,
"products": [{"id": int, "global_id": uuid, "name": ..., "price": float,
"available": bool, ...}]}]}. `currency` is the ISO code reported by the
business record itself -- trust it over countries.yaml (confirmed to vary
per-vendor even within one country: rams-st-kitts=XCD, island-liquor-dominica
via a different vendor could differ in principle, so we always read the
payload).

`price` is already a decimal value in the major unit (e.g. 6.5 = $6.50) --
NOT minor units like the WooCommerce Store API subclasses.

No per-product web page exists (app-only PDP) -- DuplicationPipeline dedups
on item['url'], so we build a synthetic-but-unique URL as the business
endpoint plus a '#<product_id>' fragment (same pattern as
afridelivery_premuni_zm.py's menu-fragment approach).

Subclasses set: name, allowed_domains, language, SLUG. Currency is read
from the payload, not hardcoded on the subclass.
"""

import html
from datetime import datetime, timezone

import scrapy

BASE_URL_TEMPLATE = "https://backend.caribeeats.com/api/business/{slug}"


class CaribeEatsBaseSpider(scrapy.Spider):
    name = None
    SLUG: str = ""
    # Set when the repo-wide pinned curl_cffi profile 403s on this tenant
    # but a different browser profile clears it. None preserves the prior
    # (repo-wide pinned) behaviour for every other subclass.
    IMPERSONATE_PROFILE: str | None = None

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _meta(self) -> dict:
        meta = {}
        if self.IMPERSONATE_PROFILE:
            meta["impersonate"] = self.IMPERSONATE_PROFILE
        return meta

    async def start(self):
        url = BASE_URL_TEMPLATE.format(slug=self.SLUG)
        yield scrapy.Request(url, callback=self.parse_business, meta=self._meta())

    def parse_business(self, response):
        try:
            data = response.json()
        except ValueError:
            self.logger.warning(f"non-JSON response at {response.url}")
            return
        currency = data.get("currency")
        categories = data.get("categories") or []
        n = 0
        for cat in categories:
            cat_name = cat.get("name")
            for p in cat.get("products") or []:
                item = self._item(p, cat_name, currency, response.url)
                if item:
                    n += 1
                    yield item
        self.logger.info(
            f"{self.name}: {n} products across {len(categories)} categories"
        )

    def _item(self, p: dict, category: str | None, currency: str | None, base_url: str):
        price = p.get("price")
        if price is None:
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        product_id = str(p.get("global_id") or p.get("id"))
        name = html.unescape(str(p.get("name") or "")).strip()
        if not name:
            return None
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": currency,
            "available": bool(p.get("available", True)),
            "url": f"{base_url}#{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
