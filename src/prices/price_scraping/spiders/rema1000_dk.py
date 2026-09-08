"""
Spider for REMA 1000 (Denmark) -- https://shop.rema1000.dk/.

The web shop is a JS SPA with no product data on the plain HTML, but
Playwright network-capture (2026-09-06) found a clean, unauthenticated
REST API on a separate host:

  GET https://api.digital.rema1000.dk/api/v1/catalog/store/1/departments-v2
      -> [{"id","name","slug","categories":[...]}] -- 15 top-level
      departments confirmed live (ids 10,20,30,40,50,60,70,80,90,100,
      110,120,130,140,160).

  GET https://api.digital.rema1000.dk/api/search/products
      ?query=&page=<n>&per_page=100&filter[departments]=<id>&sort=-popularity
      -> {"data":[{...}], "meta":{"pagination":{"current_page","last_page",
      "total"}}} -- standard page-based pagination, confirmed live (a
      2-per-page probe correctly reported total=106, last_page=53 for
      department 10).

Each product's `prices` field is a list of time-windowed price entries
(current campaign price + the regular price that takes over after the
campaign ends), not a single current price -- confirmed live 2026-09-06:
"SOLSIKKERUGBROD" carried a campaign entry (price=15, ending 2026-09-12)
and a post-campaign entry (price=22.5, starting 2026-09-13). The spider
picks the entry whose [starting_at, ending_at) window contains "now";
falls back to prices[0] if none matches (should not happen for anything
currently orderable).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://api.digital.rema1000.dk/api"
_DEPARTMENTS_URL = f"{_API_BASE}/v1/catalog/store/1/departments-v2"
_PER_PAGE = 100
_MAX_PAGES_PER_DEPT = 100  # safety cap


class Rema1000DkSpider(scrapy.Spider):
    name = "rema1000_dk"
    allowed_domains = ["api.digital.rema1000.dk"]
    currency = "DKK"
    language = "da"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_DEPARTMENTS_URL, callback=self.parse_departments)

    def parse_departments(self, response):
        try:
            departments = response.json()
        except ValueError:
            logger.error("rema1000_dk: departments response not JSON")
            return
        dept_ids = [d["id"] for d in departments if "id" in d]
        logger.info(f"rema1000_dk: {len(dept_ids)} departments")
        for dept_id in dept_ids:
            yield self._page_request(dept_id, 1)

    def _page_request(self, dept_id: int, page: int):
        url = (
            f"{_API_BASE}/search/products?query=&page={page}&per_page={_PER_PAGE}"
            f"&filter[departments]={dept_id}&sort=-popularity"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"dept_id": dept_id, "page": page},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        products = data.get("data") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, scraped_at)
            if item:
                yield item

        pagination = (data.get("meta") or {}).get("pagination") or {}
        current_page = pagination.get("current_page", response.meta["page"])
        last_page = pagination.get("last_page", current_page)
        dept_id = response.meta["dept_id"]
        if products and current_page < last_page and current_page < _MAX_PAGES_PER_DEPT:
            yield self._page_request(dept_id, current_page + 1)

    def _item(self, p: dict, scraped_at: str):
        name = (p.get("name") or "").strip()
        underline = (p.get("underline") or "").strip()
        if underline:
            name = f"{name} {underline}"
        prices = p.get("prices") or []
        if not prices:
            return None
        now = datetime.now(timezone.utc)
        chosen = None
        for entry in prices:
            start = _parse_dt(entry.get("starting_at"))
            end = _parse_dt(entry.get("ending_at"))
            if start and end and start <= now < end:
                chosen = entry
                break
        if chosen is None:
            chosen = prices[0]
        price = chosen.get("price")
        if price is None or price <= 0:
            return None
        dept = p.get("department") or {}
        category = p.get("category") or {}
        cat_parts = [c for c in (dept.get("name"), category.get("name")) if c]
        return {
            "product_id": str(p.get("id") or ""),
            "product_name": name[:500],
            "category": " > ".join(cat_parts) if cat_parts else None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://shop.rema1000.dk/vare/{p.get('id')}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }


def _parse_dt(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
