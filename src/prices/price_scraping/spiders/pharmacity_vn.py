"""Spider for Pharmacity.vn (https://www.pharmacity.vn/) -- Vietnam's
largest pharmacy chain. Wide COICOP coverage (coicop_classification:
classifier: pharmaceuticals, personal care, baby, cosmetics, supplements,
medical devices).

The storefront itself is a Next.js SPA that renders an app-level "not
found" page for direct `curl_cffi` fetches of `/`<category-slug>` --
category listings never appear in the raw HTML no matter which browser
TLS profile is used. A Playwright network-capture probe found the real
data source: a **completely open, unauthenticated** JSON API,
``api-gateway.pharmacity.vn/pmc-ecm-product/api/public/search/index``, hit
by the SPA itself for every category page. No cookies, Origin, or
Referer header are required -- confirmed with a bare ``curl_cffi`` GET
and no headers at all. This is the textbook "Playwright to discover,
plain HTTP to scrape" pattern.

Not every nav-menu path is a valid ``page_slug`` for this endpoint --
several (``tim-mach``, ``benh``, ``thuong-hieu``, ``vitamin-khoang-chat``)
are disease/brand taxonomy pages that 404/500 against this API. Only
slugs confirmed to return ``data.total > 0`` are crawled (see
``_CATEGORY_SLUGS``).

Pagination is the ``index`` query param (1-based page number), fixed
``limit=20``; ``data.total`` in the first response gives the stopping
point. Price is ``variants[0].price`` (fall back to whichever variant has
``is_sale_unit: true`` if present) -- plain VND integers, no minor-unit
division needed (VND has no subunit in practice).

Product detail page URLs are not resolvable from the category API (direct
guesses at ``/<product-slug>`` 404 -- the real PDP route nests under a
path this fetcher never discovered) so ``url`` is synthesised as the
category listing URL plus a ``#<sku>`` fragment, unique per item, to avoid
``DuplicationPipeline``'s url-based dedup collapsing every product in a
category down to one row.
"""

from __future__ import annotations

from datetime import datetime, timezone

import scrapy

_API_BASE = "https://api-gateway.pharmacity.vn/pmc-ecm-product/api/public/search/index"
_LIMIT = 20

# Verified 2026-09-06: data.total > 0 against the public search/index API.
# Excluded (404/500 "category slug not found" against this endpoint even
# though they're real nav links): tim-mach, benh, thuong-hieu,
# vitamin-khoang-chat, co-xuong-khop, da-toc-mong, di-ung, gan, ho-hap,
# khac, mat, mau, noi-tiet-chuyen-hoa, rang-ham-mat, suc-khoe-sinh-san,
# tai-mui-hong, tam-than, than-tiet-nieu, thuoc-tri-ky-sinh-trung,
# tieu-duong, tieu-hoa, truyen-nhiem, ung-thu.
_CATEGORY_SLUGS = [
    "duoc-pham",
    "cham-soc-ca-nhan",
    "cham-soc-sac-dep",
    "cham-soc-suc-khoe",
    "me-va-be",
    "san-pham-tien-loi",
    "thiet-bi-y-te-2",
    "thuc-pham-chuc-nang",
]


def _api_url(slug: str, page: int) -> str:
    return (
        f"{_API_BASE}?platform=1&index={page}&limit={_LIMIT}&total=0"
        f"&refresh=true&page=category&page_slug={slug}"
    )


class PharmacityVnSpider(scrapy.Spider):
    name = "pharmacity_vn"
    allowed_domains = ["api-gateway.pharmacity.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                _api_url(slug, 1),
                callback=self.parse,
                meta={"slug": slug, "page": 1},
            )

    def parse(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        try:
            data = response.json()["data"]
        except Exception:
            self.logger.warning("pharmacity_vn: bad JSON for slug=%s page=%d", slug, page)
            return

        items = data.get("items") or []
        total = int(data.get("total") or 0)

        for it in items:
            item = self._item(it, slug)
            if item is not None:
                yield item

        self.logger.info(
            "pharmacity_vn: slug=%s page=%d items=%d total=%d",
            slug, page, len(items), total,
        )

        if items and page * _LIMIT < total:
            nxt = page + 1
            yield scrapy.Request(
                _api_url(slug, nxt),
                callback=self.parse,
                meta={"slug": slug, "page": nxt},
            )

    def _item(self, it: dict, slug: str) -> dict | None:
        sku = it.get("sku")
        name = it.get("name")
        variants = it.get("variants") or []
        if not (sku and name and variants):
            return None
        variant = next((v for v in variants if v.get("is_sale_unit")), variants[0])
        price = variant.get("price")
        if price is None or price <= 0:
            return None
        category = it.get("category_name") or slug
        return {
            "product_id": sku,
            "product_name": name,
            "category": category,
            "price": float(price),
            "currency": self.currency,
            "available": bool(it.get("is_available_sale", True)),
            "url": f"https://www.pharmacity.vn/{slug}#{sku}",
            "language": self.language,
            "brand": it.get("brand_name"),
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
