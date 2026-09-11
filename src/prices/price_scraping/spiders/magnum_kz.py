"""
Spider for Magnum Cash&Carry (Kazakhstan) — magnum.kz.

Magnum is Kazakhstan's largest supermarket chain. The public storefront is a
Nuxt SPA whose /catalog route renders nothing server-side, but the Strapi
backend that feeds it is open and unauthenticated on port 1337:

    GET https://magnum.kz:1337/api/products?pagination[pageSize]=100&pagination[page]=N

returns the Strapi-v4 envelope {data:[{id, attributes:{...}}], meta.pagination}
with 1,392 records (2026-09-11). Verified that this endpoint is exactly the
union of the per-city `/api/new-product?cunt=N&city=<slug>` feeds: Almaty (152)
and Astana (135) share ZERO ids, because each city carries its own record for
the same SKU, and 10 cities sum to the same 1,392.

Scope caveat, recorded deliberately: this is the chain's *promotional* catalog
for the current action window (action_start/action_end, one week), not the full
assortment — magnum.kz publishes no full-assortment catalog on the web at all.
`final_price` is the shelf price during the action and `start_price` the
struck-through regular price; the spider emits `final_price` (what the shopper
pays) and carries the regular price in the URL-free `category` slot only as the
discount-programme label.

No Playwright. Category per product is not exposed by this endpoint (the
category list lives in a separate /api/new-product-catalog call that does not
join back to products), so `category` carries the discount-programme label
instead of a breadcrumb.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class MagnumKzSpider(scrapy.Spider):
    name = "magnum_kz"
    allowed_domains = ["magnum.kz"]
    currency = "KZT"

    API = "https://magnum.kz:1337/api/products"
    PAGE_SIZE = 100
    MAX_PAGES = 40  # ceiling; the real page count is ~14 and is read from meta

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    HEADERS = {
        "Accept": "application/json",
        "Origin": "https://magnum.kz",
        "Referer": "https://magnum.kz/",
    }

    def _page_request(self, page):
        url = (
            f"{self.API}?pagination[pageSize]={self.PAGE_SIZE}"
            f"&pagination[page]={page}&populate=discount_type"
        )
        return scrapy.Request(
            url,
            headers=self.HEADERS,
            callback=self.parse_page,
            meta={"page": page},
        )

    async def start(self):
        yield self._page_request(1)

    def parse_page(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("magnum_kz: JSON decode failed for %s", response.url)
            return

        items = payload.get("data") or []
        page = response.meta.get("page", 1)
        pagination = (payload.get("meta") or {}).get("pagination") or {}
        page_count = pagination.get("pageCount")
        logger.info(
            "magnum_kz: page=%s items=%s pageCount=%s total=%s",
            page,
            len(items),
            page_count,
            pagination.get("total"),
        )

        for it in items:
            attrs = it.get("attributes") or {}
            name = (attrs.get("name") or "").strip()
            price = attrs.get("final_price") or attrs.get("start_price")
            if not name or not price:
                continue
            # Strapi v4 relation envelope: discount_type.data.attributes
            dtype = ((attrs.get("discount_type") or {}).get("data") or {}).get(
                "attributes"
            ) or {}
            yield {
                "product_id": it.get("id"),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": (dtype.get("label") or "").strip() or None,
                "url": f"https://magnum.kz/catalog?product={it.get('id')}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if not items:
            return
        if page_count and page >= page_count:
            return
        if page >= self.MAX_PAGES:
            logger.warning(
                "magnum_kz: stopped at MAX_PAGES=%s with pageCount=%s — "
                "the remaining pages were NOT collected",
                self.MAX_PAGES,
                page_count,
            )
            return
        yield self._page_request(page + 1)
