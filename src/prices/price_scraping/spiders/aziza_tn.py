"""
Aziza (Tunisia) -- https://www.aziza.tn/. Magasins Aziza, a 350+ store
supermarket chain. No online shop/PDP layer -- the public site is a
marketing + weekly-flyer viewer for the loyalty app (`tn.aziza.app`), backed
by an open, unauthenticated JSON API at `btoc.azizacdn.com` (confirmed live
2026-09-01 via a Playwright network trace of https://www.aziza.tn/).

`GET /backend/public/api/aziza/getProducts` with no date filter returns the
ENTIRE historical promo-flyer archive back to 2022 (18,595 items, most with
`price: 0` once their promo window has lapsed) -- this is NOT a live catalog
snapshot and must not be walked whole. The site's own homepage JS instead
scopes every request to the CURRENT week's `oc_debut`/`oc_fin` bounds (the
"Promo de la semaine" circular). Aziza's promo weeks run Wednesday->Tuesday
(confirmed from a "Mercredi prochain" teaser item whose `oc_debut` was the
next Wednesday while today's live query used last Wednesday -> today as
`oc_fin`). This spider reproduces that same current-week window rather than
walking the full archive, so each run captures this week's real,
currently-charged promo prices only -- re-running weekly picks up whatever
promo set is active that week, matching Aziza's own cadence.

`page=`/`per_page=` (not `offset=`, which the backend silently ignores and
always returns page 1) is the real pagination param -- confirmed by diffing
`offset=0` vs `offset=17175` (100% id overlap) against `page=1` vs `page=2`
(0% overlap).

Prices are already plain TND float amounts (e.g. 0.47, 26.5, 8.49) -- not
minor units, matching the sibling `carrefour_tn` finding for the same
currency. No `currency` field is ever populated in the payload (always
null) so TND is set at the spider level per countries.yaml.

No per-product URL exists (Aziza has no e-commerce PDP), so `url` uses the
item's own per-SKU CDN image path (`images`/`small_image`), which is stable
and unique per product -- the closest thing to a canonical resource this
source has. Cold re-fetch verification for this source means re-querying
the API by id/name and confirming price, not visiting a web page.
"""

import logging
from datetime import datetime, timedelta, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://btoc.azizacdn.com/backend/public/api/aziza/getProducts"
_PER_PAGE = 1000
_MAX_PAGES = 20  # 20 * 1000 = 20,000 row ceiling; current-week window measured at ~362


def _current_week_bounds():
    """Aziza's promo weeks run Wednesday -> Tuesday (inclusive)."""
    today = datetime.now(timezone.utc).date()
    days_since_wed = (today.weekday() - 2) % 7  # Monday=0 ... Wednesday=2
    start = today - timedelta(days=days_since_wed)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


class AzizaTnSpider(scrapy.Spider):
    name = "aziza_tn"
    allowed_domains = ["azizacdn.com"]
    currency = "TND"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _url(self, page: int) -> str:
        oc_debut, oc_fin = _current_week_bounds()
        return (
            f"{_API}?oc_debut={oc_debut}&oc_fin={oc_fin}"
            f"&per_page={_PER_PAGE}&page={page}"
        )

    async def start(self):
        yield scrapy.Request(self._url(1), callback=self.parse_page, meta={"page": 1})

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning("aziza_tn: non-JSON response at page=%d", page)
            return
        items = payload.get("items") or []
        paging = payload.get("paging") or {}
        n = 0
        for item in items:
            row = self._row(item)
            if row is not None:
                n += 1
                yield row
        logger.info(
            "aziza_tn page=%d rows=%d last_page=%s",
            page,
            n,
            paging.get("last_page"),
        )
        last_page = paging.get("last_page") or 1
        if page < min(last_page, _MAX_PAGES):
            nxt = page + 1
            yield scrapy.Request(
                self._url(nxt), callback=self.parse_page, meta={"page": nxt}
            )

    def _row(self, item: dict):
        name = (item.get("name") or "").strip()
        if not name:
            return None
        price = item.get("price")
        if price is None or price in (0, "0", 0.0):
            return None
        product_id = item.get("id")
        if product_id is None:
            return None
        plus = (item.get("plus") or "").strip()
        product_name = f"{name} ({plus})" if plus else name
        url = item.get("images") or item.get("small_image") or ""
        return {
            "product_id": str(product_id),
            "product_name": product_name[:500],
            "category": item.get("category_name"),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
