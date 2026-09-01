"""
Melat Shop (Afghanistan) -- a named first-party grocery/household merchant
sold through the Dara.af marketplace (https://dara.af/), NOT Dara itself.

Dara.af is a general Next.js marketplace with an open backend API at
backend.dara.af (Laravel-style REST, confirmed live 2026-09-01 via a
Playwright network trace of https://dara.af/en/shop -- no auth, no WAF).
The marketplace has only 5 registered sellers total
(GET https://backend.dara.af/api/v1/sellers): Zala, Easy Shop, Melat Shop,
Asan Mart, and an inactive "Haftseen" account with zero published products.
Of those, Melat Shop is the one genuine grocery merchant -- sampling its
960-product catalog shows a supermarket mix of fresh dairy (doogh, yogurt),
packaged food (spices, biscuits, pizza cheese), baby feeding supplies and
personal care, vs. Zala (mostly beauty/fragrance/fashion), Easy Shop (mostly
books/electronics) and Asan Mart (mostly electronics/home) which are not
food-channel. One product's own `attributes` list even names the supplier
as "سوپرمارکیت‌های هفت‌سین" (Haftsin Supermarkets) / brand "هفت‌سین" for a
fresh-dairy line -- Melat Shop is a real bricks-and-mortar-adjacent grocer's
storefront on the platform, not a marketplace-wide blend.

This spider hits ONLY this seller's slice of the catalog via
`filters[seller_id]=<melat-shop-id>` -- it does not touch Dara's other 4
sellers, so there is no double-count risk with any future whole-marketplace
Dara spider (none exists in this repo yet).

Prices are plain AFN amounts (not minor units) confirmed against multiple
live examples (e.g. "Fresh Doogh 300ml" = 20 AFN, a power bank = 5,200 AFN --
both match realistic Kabul retail prices at face value). `?locale=en` was
used for clean, boilerplate-free English product names; category is the
product's own first breadcrumb category from Dara's taxonomy. A product can
carry more than one price variant (e.g. a 300ml vs 500ml size); each variant
is emitted as its own row with the variant id folded into both the URL and
`product_id` so DuplicationPipeline's url-based dedup does not collapse
same-product size variants into one row.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://backend.dara.af/api/v1/products"
_SELLER_ID = "019d5e14-465c-76d7-a165-e8dae351dba3"
_PER_PAGE = 100
_MAX_PAGES = 20  # 20 * 100 = 2,000 rows ceiling; catalog measured at 960


class MelatShopAfSpider(scrapy.Spider):
    name = "melat_shop_af"
    allowed_domains = ["backend.dara.af"]
    currency = "AFN"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _url(self, page: int) -> str:
        return (
            f"{_API}?per_page={_PER_PAGE}&page={page}&locale=en"
            f"&filters[seller_id]={_SELLER_ID}"
        )

    async def start(self):
        yield scrapy.Request(self._url(1), callback=self.parse_page, meta={"page": 1})

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning("melat_shop_af: non-JSON response at page=%d", page)
            return
        data = (payload.get("data") or {}).get("data") or []
        meta = (payload.get("data") or {}).get("meta") or {}
        n = 0
        for product in data:
            for row in self._rows(product):
                n += 1
                yield row
        logger.info(
            "melat_shop_af page=%d rows=%d last_page=%s",
            page,
            n,
            meta.get("last_page"),
        )
        last_page = meta.get("last_page") or 1
        if page < min(last_page, _MAX_PAGES):
            nxt = page + 1
            yield scrapy.Request(
                self._url(nxt), callback=self.parse_page, meta={"page": nxt}
            )

    def _rows(self, product: dict):
        name = (product.get("name") or "").strip()
        if not name:
            return
        slug = product.get("slug") or product.get("id")
        product_id = product.get("id")
        categories = product.get("categories") or []
        category = categories[0].get("name") if categories else None
        variants = product.get("variants") or []
        multi = len(variants) > 1
        scraped_at = datetime.now(timezone.utc).isoformat()

        for variant in variants:
            price = variant.get("price")
            if price is None or price in (0, "0"):
                continue
            option_values = variant.get("option_values") or []
            size_label = None
            if multi and option_values:
                size_label = option_values[0].get("name")
            product_name = f"{name} ({size_label})" if size_label else name
            variant_id = variant.get("id")
            yield {
                "product_id": str(variant_id or f"{product_id}"),
                "product_name": product_name[:500],
                "category": category,
                "price": str(price),
                "currency": variant.get("currency") or self.currency,
                "available": (variant.get("stock") or 0) > 0,
                "url": f"https://dara.af/en/shop/{slug}?id={product_id}&v={variant_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
