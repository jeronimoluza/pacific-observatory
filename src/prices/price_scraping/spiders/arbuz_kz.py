"""
Spider for Arbuz.kz (Kazakhstan) -- https://arbuz.kz/.

SPA behind Cloudflare (challenge-platform scripts present, but plain
curl_cffi requests to the API host clear it -- no browser fingerprint
needed for the endpoints below). Playwright network-capture (2026-09-06)
found the app's anonymous auth + catalog flow:

  1. POST /api/v1/auth/token {"consumer":"arbuz-kz.web.desktop",
     "key":"M3KAMKD0esxMQUcIBBnYD8sl1LUS6OQr"} -> {"data":{"token":
     "<JWT>", "store":{"id":"1","cityId":"21",...}}}. Both the consumer
     name and key are public constants baked into the frontend bundle;
     the endpoint mints a fresh long-lived (100-year expiry) anonymous
     bearer token on demand -- no login required. Reused for the whole
     crawl (send as `Authorization: Bearer <token>`, NOT the `?token=`
     query param the browser sometimes uses -- the query-param form
     401'd in testing, the header form worked).
  2. GET /api/v1/shop/catalog/<top_category_id>?where[available][e]=0&page=<n>
     -> {"data":{"catalogCount",...,"products":{"data":[...],
     "page":{"current","last","count"}}}}. Each top-level category is
     `isElasticsearch:true` and its listing already aggregates every
     descendant subcategory's products (confirmed live 2026-09-06:
     category 14 "Вода и напитки" reports count=622 total products with
     no subcategory id ever passed) -- so the crawl only needs the ~21
     top-level ids from the homepage nav, not a full category tree walk.
     Page size is server-capped at 40 regardless of a `limit=` override.

Confirmed live 2026-09-06: category 225161 ("Молоко, сыр и яйца"),
product 20069 "Молоко Lactel с витамином D 2,5% 1 л", priceActual=666
(current price), pricePrevious=784 (pre-discount) KZT -- plain KZT
integers, no minor-unit scaling.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://arbuz.kz/api/v1"
_AUTH_BODY = (
    '{"consumer":"arbuz-kz.web.desktop","key":"M3KAMKD0esxMQUcIBBnYD8sl1LUS6OQr"}'
)
# Top-level category ids from the homepage nav, confirmed live 2026-09-06.
_TOP_CATEGORY_IDS = [
    14, 16, 19, 20, 224407, 224645, 225161, 225162, 225164, 225165,
    225166, 225167, 225169, 225183, 225253, 225602, 225606, 225752,
    225775, 225782, 225945,
]
MAX_PAGES_PER_CATEGORY = 60  # safety cap; largest observed category was 16 pages


class ArbuzKzSpider(scrapy.Spider):
    name = "arbuz_kz"
    allowed_domains = ["arbuz.kz"]
    currency = "KZT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bearer_token = None

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/auth/token",
            method="POST",
            body=_AUTH_BODY,
            headers={"Content-Type": "application/json"},
            callback=self.parse_auth,
        )

    def parse_auth(self, response):
        try:
            self.bearer_token = response.json()["data"]["token"]
        except (ValueError, KeyError):
            logger.error("arbuz_kz: could not obtain bearer token")
            return
        for cat_id in _TOP_CATEGORY_IDS:
            yield self._page_request(cat_id, 1)

    def _page_request(self, cat_id: int, page: int):
        url = f"{_BASE}/shop/catalog/{cat_id}?where[available][e]=0&page={page}"
        return scrapy.Request(
            url,
            headers={"Authorization": f"Bearer {self.bearer_token}"},
            callback=self.parse_page,
            meta={"cat_id": cat_id, "page": page},
        )

    def parse_page(self, response):
        try:
            data = response.json()["data"]
        except (ValueError, KeyError):
            return
        products = (data.get("products") or {}).get("data") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, data.get("name"), scraped_at)
            if item:
                yield item

        page_info = (data.get("products") or {}).get("page") or {}
        current = page_info.get("current", response.meta["page"])
        last = page_info.get("last", current)
        cat_id = response.meta["cat_id"]
        if products and current < last and current < MAX_PAGES_PER_CATEGORY:
            yield self._page_request(cat_id, current + 1)

    def _item(self, p: dict, category_name, scraped_at: str):
        name = (p.get("name") or "").strip()
        price = p.get("priceActual")
        if price is None:
            price = p.get("pricePrevious")
        if not name or price is None:
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        return {
            "product_id": str(p.get("id") or ""),
            "product_name": name[:500],
            "category": p.get("catalogName") or category_name,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://arbuz.kz{p.get('uri')}" if p.get("uri") else "https://arbuz.kz/",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
