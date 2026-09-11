"""
Sawdagar (Afghanistan) -- a general marketplace with an open, unauthenticated
REST catalog API at sawdagaraf.com/api/products.

Verified live 2026-09-11: GET https://sawdagaraf.com/api/products?page=N&limit=100
requires no auth and returns real pagination metadata
({"products": [...], "total": 883, "totalPages": 89, "pagination": {...}}).
Enumerability proof: page=1 and page=2 return zero overlapping product ids
(confirmed against the default per_page=10 as well as limit=100). This is a
distinct signal from an earlier attempt to walk category listing pages
(/categories/<slug>), which return a FIXED 3-item "featured" set regardless
of ?page= -- that path does not paginate and is NOT used here.

Prices are the `retailPrice` field, plain AFN amounts (not minor units) --
cross-checked against the product-detail page's own rendered
`"priceLabel":"AFN","priceValue":"؋850"` for the same id, which matches
retailPrice:850 1:1. Category taxonomy spans general merchandise including
food (`/categories/food`, `/categories/milk`, `/categories/juice`,
`/categories/curd`, `/categories/baverages` all present in the site's own
nav), electronics, clothing, medical, home, etc -- a genuine cross-COICOP
marketplace, not a single-division specialty store.

Multi-vendor: each product carries its own `supplier` (company name +
province), similar in shape to a Dokan/multi-seller WooCommerce site, but
this is a bespoke Next.js/Node backend, not WooCommerce -- no generic
template fits.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://sawdagaraf.com/api/products"
_PER_PAGE = 100
_MAX_PAGES = 20  # 20 * 100 = 2,000 rows ceiling; catalog measured at 883


class SawdagarAfSpider(scrapy.Spider):
    name = "sawdagar_af"
    allowed_domains = ["sawdagaraf.com"]
    currency = "AFN"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _url(self, page: int) -> str:
        return f"{_API}?page={page}&limit={_PER_PAGE}"

    async def start(self):
        yield scrapy.Request(self._url(1), callback=self.parse_page, meta={"page": 1})

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning("sawdagar_af: non-JSON response at page=%d", page)
            return
        products = payload.get("products") or []
        total_pages = payload.get("totalPages") or 1
        n = 0
        for product in products:
            row = self._row(product)
            if row:
                n += 1
                yield row
        logger.info(
            "sawdagar_af page=%d rows=%d totalPages=%s", page, n, total_pages
        )
        if page < min(total_pages, _MAX_PAGES):
            nxt = page + 1
            yield scrapy.Request(
                self._url(nxt), callback=self.parse_page, meta={"page": nxt}
            )

    def _row(self, product: dict):
        if product.get("isDeleted") or product.get("status") not in (None, "approved"):
            return None
        name = (product.get("nameEn") or product.get("nameDr") or "").strip()
        if not name:
            return None
        price = product.get("retailPrice")
        try:
            if price is None or float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None
        product_id = product.get("id")
        category = product.get("category") or {}
        category_name = (category.get("nameEn") or "").strip() or None
        scraped_at = datetime.now(timezone.utc).isoformat()
        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category_name,
            "price": str(price),
            "currency": self.currency,
            "available": (product.get("stock") or 0) > 0,
            "url": f"https://sawdagaraf.com/products/{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
