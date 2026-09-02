"""DeCA Commissary Click2Go -- Andersen AFB, Guam.

https://shop.commissaries.com/ (Defense Commissary Agency's "Click2Go" web
storefront) runs on a Freshop-family catalog API, but at a DIFFERENT host
than the existing `_freshop_base.FreshopBaseSpider` tenants
(api.freshop.ncrcloud.com): this tenant lives at
api.prd.freshop.retail.ncrgov.com, app_key=deca. Confirmed by reading the
storefront's own embedded script tag
(`asset.prd.freshop.retail.ncrgov.com/freshop.js?app_key=deca&allow_bots=true
&api_url=https://api.prd.freshop.retail.ncrgov.com/`) -- the site explicitly
declares `allow_bots=true`. Because the host differs from the shared base
class's hardcoded `_BASE`, this is a standalone spider rather than a
`_freshop_base` subclass (per the onboarding rule against modifying shared
spider bases) -- the pagination shape (`/2/products?app_key=...&limit=100&
skip=N&store_id=...&sort=id`, `skip` honored, `limit` capped at 100) is
otherwise identical.

DeCA operates 238 commissary stores worldwide (verified via
`/2/stores?app_key=deca`); only two are in Guam: store_id 5944 (Andersen
AFB, 8,418 items) and 5947 (Orote/Naval Base Guam, 8,387 items). Spot-checks
across both show they are the SAME operator's near-duplicate catalog (shared
SKUs price identically, e.g. "Heinz Picnic Pack 3 ct bottle" = $4.98 at
both) -- onboarding both would be the same-shelf-twice mistake the skill
warns against, so only the larger store (5944) is scaffolded here.

Channel caveat: DeCA commissaries are a subsidized/at-cost benefit for
authorized US military-affiliated patrons, not an open-market retailer --
mirrors the existing `costuless_ky` / `malaeimi_wholesale_as` precedent of
substituting `channel: wholesale` when the schema's retail-channel enum has
no dedicated "non-market/subsidized" value. This is deliberate so PPP
analysis never blends commissary prices into Guam's civilian retail-price
series (per a standing note in the Guam inventory file).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://api.prd.freshop.retail.ncrgov.com"
_PRODUCTS = _BASE + "/2/products"
_PAGE_SIZE = 100
_APP_KEY = "deca"
_STORE_ID = "5944"  # Andersen AFB, Guam


class DecaCommissaryGuSpider(scrapy.Spider):
    name = "deca_commissary_gu"
    allowed_domains = ["api.prd.freshop.retail.ncrgov.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.8,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield self._page_request(0)

    def _page_request(self, skip: int):
        return scrapy.Request(
            f"{_PRODUCTS}?app_key={_APP_KEY}&limit={_PAGE_SIZE}"
            f"&skip={skip}&store_id={_STORE_ID}&sort=id",
            callback=self.parse_page,
            meta={"skip": skip},
            headers={"Accept": "application/json"},
        )

    def parse_page(self, response):
        skip = response.meta["skip"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"{self.name}: non-JSON response at skip={skip}")
            return

        items = payload.get("items") or []
        total = payload.get("total") or 0
        logger.info(f"{self.name}: skip={skip} count={len(items)} total={total}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item = self._item(it, scraped_at)
            if item:
                yield item

        next_skip = skip + _PAGE_SIZE
        if len(items) >= _PAGE_SIZE and next_skip < total:
            yield self._page_request(next_skip)

    def _item(self, it: dict, scraped_at: str):
        name = it.get("name")
        price = it.get("unit_price")
        if not name or price is None or price <= 0:
            return None
        return {
            "product_id": it.get("upc")
            or it.get("reference_id")
            or str(it.get("id", "")),
            "product_name": name,
            "category": it.get("pos_department") or None,
            "price": str(price),
            "currency": self.currency,
            "available": not it.get("is_suppressed", False),
            "url": it.get("canonical_url") or "https://shop.commissaries.com/shop",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(
            f"{self.name}: request failed {failure.request.url} — {failure.value!r}"
        )
