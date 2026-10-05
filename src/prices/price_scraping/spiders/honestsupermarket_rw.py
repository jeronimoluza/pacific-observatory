"""
Spider for N.Honest Supermarket (Rwanda) — https://www.honestsupermarket.com/.

The storefront's JavaScript calls a public paginated JSON API at
`/api/products`. Re-verified live 2026-08-31: `?limit=5&page=1` returned
5,174 products over 1,035 pages, with grocery categories such as fruits and
vegetables, cooking oil, rice, dairy, meat/fish, water, juices and soft
drinks. The API does not expose stable product-detail URLs in the probed
payload, so item URLs point to the API surface with product/size identifiers.
"""

from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

_BASE = "https://www.honestsupermarket.com"
_PRODUCTS_API = f"{_BASE}/api/products"
_PER_PAGE = 100
_MAX_PAGES = 300


class HonestSupermarketRwSpider(scrapy.Spider):
    name = "honestsupermarket_rw"
    allowed_domains = ["honestsupermarket.com", "www.honestsupermarket.com"]
    currency = "RWF"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(self._page_url(1), callback=self.parse_page, meta={"page": 1})

    def _page_url(self, page: int) -> str:
        return f"{_PRODUCTS_API}?{urlencode({'limit': _PER_PAGE, 'page': page})}"

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            self.logger.warning("honestsupermarket_rw: non-JSON response at %s", response.url)
            return

        products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(products, list) or not products:
            return

        page = int(payload.get("page") or response.meta["page"])
        total_pages = int(payload.get("totalPages") or page)
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            yield from self._items(product, scraped_at)

        if page < total_pages and page < _MAX_PAGES:
            yield scrapy.Request(
                self._page_url(page + 1),
                callback=self.parse_page,
                meta={"page": page + 1},
            )

    def _items(self, product: dict, scraped_at: str):
        product_id = str(product.get("_id") or "").strip()
        name = str(product.get("name") or "").strip()
        if not product_id or not name:
            return

        category_obj = product.get("category") or {}
        category = (
            category_obj.get("name") if isinstance(category_obj, dict) else category_obj
        )
        available = (
            str(product.get("status") or "").lower() == "active"
            and not bool(product.get("notAvailable"))
        )
        sizes = product.get("sizes") or []
        if not isinstance(sizes, list) or not sizes:
            sizes = [{"_id": None, "name": None, "price": product.get("price")}]

        for size in sizes:
            if not isinstance(size, dict):
                continue
            price = size.get("price", product.get("price"))
            if price in (None, ""):
                continue

            size_id = size.get("_id")
            size_name = str(size.get("name") or "").strip()
            has_named_size = bool(size_name and size_name.lower() != "unnamed size")
            row_name = f"{name} ({size_name})" if has_named_size else name
            row_id = f"{product_id}:{size_id}" if size_id else product_id

            yield {
                "product_id": row_id,
                "product_name": row_name[:500],
                "category": category,
                "price": str(price).replace(",", ""),
                "currency": self.currency,
                "available": available,
                "url": f"{_PRODUCTS_API}#{row_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
